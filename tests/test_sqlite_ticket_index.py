from __future__ import annotations

import gc
import json
import os
import selectors
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from planfile import Planfile
from planfile.api import server
from planfile.cli.commands import app
from planfile.core.fastio import mirror_path
from planfile.core.sqlite_index import SQLiteTicketIndex
from planfile.core.store import TicketIndexContentionError, TicketUpdatedAtConflictError


def _disable_archive(pf: Planfile) -> None:
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    pf.store._write_config(config)


def test_index_reads_release_descriptors_without_cyclic_gc(tmp_path, monkeypatch):
    index = SQLiteTicketIndex(tmp_path / "index.sqlite")
    signature = ("source", 1)
    index.rebuild([], signature)
    connect = sqlite3.connect
    opened = []

    def capture(*args, **kwargs):
        connection = connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", capture)
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    descriptor_root = Path("/proc/self/fd")
    try:
        before = len(os.listdir(descriptor_root)) if descriptor_root.is_dir() else None
        for _ in range(100):
            assert index.status(signature)["current"]
            assert index.is_current(signature)
        assert len(opened) == 200
        for connection in opened:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                connection.execute("SELECT 1")
        if before is not None:
            assert len(os.listdir(descriptor_root)) <= before + 2
    finally:
        if was_enabled:
            gc.enable()


@pytest.mark.parametrize("fail", [False, True])
def test_index_operation_commits_or_rolls_back_then_closes(tmp_path, fail):
    index = SQLiteTicketIndex(tmp_path / "index.sqlite")
    index.rebuild([], ("source", 1))
    connection = None
    try:
        with index._connection() as connection:
            connection.execute("INSERT INTO meta VALUES('lifetime-test', 'present')")
            if fail:
                raise RuntimeError("abort transaction")
    except RuntimeError:
        assert fail
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    with index._connection() as observer:
        row = observer.execute("SELECT value FROM meta WHERE key='lifetime-test'").fetchone()
    assert (row is None) == fail


@pytest.mark.parametrize("hook", ["_initialize", "_ensure_routes"])
def test_failed_index_setup_closes_its_connection(tmp_path, monkeypatch, hook):
    connect = sqlite3.connect
    opened = []

    def capture(*args, **kwargs):
        connection = connect(*args, **kwargs)
        opened.append(connection)
        return connection

    def fail(*args):
        raise RuntimeError("setup refused")

    monkeypatch.setattr(sqlite3, "connect", capture)
    monkeypatch.setattr(SQLiteTicketIndex, hook, staticmethod(fail))
    with pytest.raises(RuntimeError, match="setup refused"):
        SQLiteTicketIndex(tmp_path / "index.sqlite")._connect()
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")


def test_busy_rebuild_preserves_independent_writer_and_index(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Committed before rebuild")
    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    inode = index.path.stat().st_ino
    code = (
        "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
        "c.execute('BEGIN IMMEDIATE'); print('held',flush=True); "
        "sys.stdin.readline(); c.rollback(); c.close()"
    )
    holder = subprocess.Popen([sys.executable, "-u", "-c", code, str(index.path)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)
    connect = SQLiteTicketIndex._connect

    def short_wait(self):
        connection = connect(self)
        connection.execute("PRAGMA busy_timeout=10")
        return connection

    try:
        with selectors.DefaultSelector() as ready:
            ready.register(holder.stdout, selectors.EVENT_READ)
            assert ready.select(10), "Independent writer did not start"
        assert holder.stdout.readline().strip() == "held"
        monkeypatch.setattr(SQLiteTicketIndex, "_connect", short_wait)
        with pytest.raises(TicketIndexContentionError, match="ticket_index_rebuild_busy"):
            pf.store.ensure_ticket_index(force=True)
        assert holder.poll() is None
        assert index.path.stat().st_ino == inode
        assert index.get_ticket(ticket.id)["name"] == "Committed before rebuild"
        assert pf.store._locate_ticket_source(ticket.id)[1]["name"] == "Committed before rebuild"
    finally:
        _, error = holder.communicate("release\n", timeout=10)
        assert holder.returncode == 0, error
    assert pf.store.ensure_ticket_index(force=True)["current"]


@pytest.mark.parametrize("code,message", [
    (5, "localized"), (6, "localized"), (5 | (2 << 8), "localized"),
    (6 | (1 << 8), "localized"), (None, "database is locked"),
    (None, "database table is locked: tickets"),
])
def test_busy_rebuild_never_resets_or_replays(tmp_path, monkeypatch, code, message):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_ticket(name="Retained")
    pf.store.configure_ticket_index(True)
    error = sqlite3.OperationalError(message)
    if code is not None:
        error.sqlite_errorcode = code
    attempts = []

    def busy(*args, **kwargs):
        attempts.append(True)
        raise error

    def forbidden(*args):
        raise AssertionError("A busy index must not be reset")

    monkeypatch.setattr(SQLiteTicketIndex, "rebuild", busy)
    monkeypatch.setattr(SQLiteTicketIndex, "reset", forbidden)
    with pytest.raises(TicketIndexContentionError, match="ticket_index_rebuild_busy") as raised:
        pf.store.ensure_ticket_index(force=True)
    assert raised.value.__cause__ is error
    assert len(attempts) == 1


def test_sqlite_rebuild_streams_records_in_bounded_batches(tmp_path):
    class TrackedRecord(dict):
        active = 0
        maximum = 0

        def __init__(self, number: int):
            type(self).active += 1
            type(self).maximum = max(type(self).maximum, type(self).active)
            ticket_id = f"PLF-{number}"
            super().__init__(
                id=ticket_id,
                sprint="current",
                status="open",
                priority="normal",
                source=None,
                queue="default",
                created_at=None,
                updated_at=None,
                position=number,
                ticket_json=json.dumps({"id": ticket_id}),
                summary_json=json.dumps({"id": ticket_id}),
                blocked_by=["PLF-0"] if number else [],
            )

        def __del__(self):
            type(self).active -= 1

    def records():
        for number in range(257):
            yield TrackedRecord(number)

    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")
    count = index.rebuild(records(), ("source", 1), batch_size=16)
    gc.collect()

    assert count == 257
    assert TrackedRecord.active == 0
    assert TrackedRecord.maximum <= 16
    with sqlite3.connect(index.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 257
        assert connection.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0] == 256


def test_sqlite_rebuild_keeps_last_committed_snapshot_readable(tmp_path):
    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")

    def record(ticket_id: str, name: str) -> dict:
        ticket = {"id": ticket_id, "name": name}
        encoded = json.dumps(ticket)
        return {
            "id": ticket_id,
            "sprint": "current",
            "status": "open",
            "priority": "normal",
            "source": None,
            "queue": "default",
            "created_at": None,
            "updated_at": None,
            "position": 0,
            "ticket_json": encoded,
            "summary_json": encoded,
            "blocked_by": [],
        }

    index.rebuild([record("PLF-1", "Committed")], ("source", 1))
    rebuild_started = threading.Event()
    finish_rebuild = threading.Event()

    def delayed_records():
        rebuild_started.set()
        assert finish_rebuild.wait(timeout=5)
        yield record("PLF-2", "Replacement")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(index.rebuild, delayed_records(), ("source", 2))
        assert rebuild_started.wait(timeout=5)
        try:
            summaries, total = index.list_summaries(
                sprint="all", filters={}, offset=0, limit=1
            )
        finally:
            finish_rebuild.set()
        assert future.result(timeout=5) == 1

    assert total == 1
    assert summaries == [{"id": "PLF-1", "name": "Committed"}]
    replacement, replacement_total = index.list_summaries(
        sprint="all", filters={}, offset=0, limit=1
    )
    assert replacement_total == 1
    assert replacement == [{"id": "PLF-2", "name": "Replacement"}]


def test_concurrent_index_signature_reads_share_one_filesystem_scan(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_ticket(name="Signature coalescing")
    pf.store.configure_ticket_index(True)
    pf.store._invalidate_ticket_index_signature_cache()
    original = pf.store._ticket_index_signature
    scan_started = threading.Event()
    finish_scan = threading.Event()
    calls = 0

    def slow_signature():
        nonlocal calls
        calls += 1
        scan_started.set()
        assert finish_scan.wait(timeout=5)
        return original()

    monkeypatch.setattr(pf.store, "_ticket_index_signature", slow_signature)
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(pf.store._cached_ticket_index_signature) for _ in range(16)]
        assert scan_started.wait(timeout=5)
        finish_scan.set()
        signatures = [future.result(timeout=5) for future in futures]

    assert calls == 1
    assert all(signature == signatures[0] for signature in signatures)


def test_local_mutation_invalidates_cached_index_signature(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_ticket(name="Before signature")
    pf.store.configure_ticket_index(True)

    before = pf.store._cached_ticket_index_signature()
    pf.create_ticket(name="After signature")
    after = pf.store._cached_ticket_index_signature()

    assert after != before
    assert pf.store.require_current_ticket_index(signature=after)["current"] is True


def test_sqlite_renders_operational_projection_without_python_object_graph(tmp_path):
    ticket = {
        "id": "PLF-1",
        "name": "Operational projection",
        "status": "open",
        "history": [{"large": "journal"}],
        "dsl": "large dsl",
        "source": {"tool": "test", "context": {"large": "source context"}},
        "outputs": {
            "notes": ["large note"],
            "artifacts": ["artifact://large"],
            "result": {"ready": True},
        },
    }
    encoded = json.dumps(ticket, separators=(",", ":"))
    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")
    index.rebuild(
        [
            {
                "id": ticket["id"],
                "sprint": "current",
                "status": "open",
                "priority": "normal",
                "source": "test",
                "queue": "default",
                "created_at": None,
                "updated_at": None,
                "position": 0,
                "ticket_json": encoded,
                "summary_json": encoded,
                "blocked_by": [],
            }
        ],
        ("source", 1),
    )

    body, total, count = index.render_operational_payloads(
        sprint="all", filters={}, offset=0, limit=100
    )

    assert total == 1
    assert count == 1
    assert json.loads(body) == [server._ticket_operational_payload(ticket)]


def test_unrelated_ticket_queries_do_not_share_a_response_build_lock(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_ticket(name="Concurrent query")
    pf.store.configure_ticket_index(True)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    slow_started = threading.Event()
    finish_slow = threading.Event()
    original = pf.store.indexed_ticket_summaries

    def summaries(**kwargs):
        if kwargs["filters"].get("source") == "slow":
            slow_started.set()
            assert finish_slow.wait(timeout=5)
        return original(**kwargs)

    monkeypatch.setattr(pf.store, "indexed_ticket_summaries", summaries)
    slow_filters = {"source": "slow"}
    fast_number = 0
    while True:
        fast_filters = {"source": f"fast-{fast_number}"}
        slow_key = (str(pf.store.project_dir), "all", tuple(slow_filters.items()), 0, 1, "summary")
        fast_key = (str(pf.store.project_dir), "all", tuple(fast_filters.items()), 0, 1, "summary")
        if server._ticket_list_response_build_lock(slow_key) is not server._ticket_list_response_build_lock(fast_key):
            break
        fast_number += 1

    def response(filters):
        return server._ticket_list_response(
            pf,
            sprint="all",
            filters=filters,
            offset=0,
            limit=1,
            view="summary",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(response, slow_filters)
        assert slow_started.wait(timeout=5)
        fast = pool.submit(response, fast_filters)
        try:
            assert fast.result(timeout=1).status_code == 200
        finally:
            finish_slow.set()
        assert slow.result(timeout=5).status_code == 200


def test_identical_ticket_queries_still_share_one_response_build(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_ticket(name="Shared query")
    pf.store.configure_ticket_index(True)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    first_started = threading.Event()
    finish_first = threading.Event()
    calls = 0
    calls_lock = threading.Lock()
    original = pf.store.indexed_ticket_summaries

    def summaries(**kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
            current_call = calls
        if current_call == 1:
            first_started.set()
            assert finish_first.wait(timeout=5)
        return original(**kwargs)

    monkeypatch.setattr(pf.store, "indexed_ticket_summaries", summaries)

    def response():
        return server._ticket_list_response(
            pf,
            sprint="all",
            filters={"source": "shared"},
            offset=0,
            limit=1,
            view="summary",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(response)
        assert first_started.wait(timeout=5)
        second = pool.submit(response)
        time.sleep(0.1)
        try:
            assert calls == 1
        finally:
            finish_first.set()
        assert first.result(timeout=5).status_code == 200
        assert second.result(timeout=5).status_code == 200
    assert calls == 1


def test_slow_archive_operational_build_never_blocks_summary_status(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_ticket(name="Workload isolation")
    pf.store.configure_ticket_index(True)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    slow_started = threading.Event()
    finish_slow = threading.Event()
    original = pf.store.indexed_ticket_operational_response

    def operational_response(**kwargs):
        if not kwargs["filters"]:
            slow_started.set()
            assert finish_slow.wait(timeout=5)
        return original(**kwargs)

    monkeypatch.setattr(
        pf.store,
        "indexed_ticket_operational_response",
        operational_response,
    )

    def slow_response():
        return server._ticket_list_response(
            pf,
            sprint="all",
            filters={},
            offset=0,
            limit=1000,
            view="operational",
        )

    def status_response():
        return server._ticket_list_response(
            pf,
            sprint="all",
            filters={"source": "status"},
            offset=0,
            limit=1,
            view="summary",
        )

    def filtered_operational_response():
        return server._ticket_list_response(
            pf,
            sprint="all",
            filters={"status": "open"},
            offset=0,
            limit=500,
            view="operational",
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        slow = pool.submit(slow_response)
        assert slow_started.wait(timeout=5)
        status = pool.submit(status_response)
        filtered = pool.submit(filtered_operational_response)
        try:
            assert status.result(timeout=1).status_code == 200
            assert filtered.result(timeout=1).status_code == 200
        finally:
            finish_slow.set()
        assert slow.result(timeout=5).status_code == 200


def test_heavy_archive_operational_builds_have_bounded_concurrency():
    active = 0
    maximum = 0
    lock = threading.Lock()

    def build():
        nonlocal active, maximum
        with server._ticket_list_workload_slot(
            sprint="all",
            filters={},
            limit=1000,
            view="operational",
        ):
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.05)
            with lock:
                active -= 1

    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda _number: build(), range(12)))

    assert maximum == 4


def test_sqlite_index_serves_get_without_reparsing_sprint_files(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Indexed ticket", priority="high")

    status = pf.store.configure_ticket_index(True)
    assert status["current"] is True
    assert status["tickets"] == 1

    def unexpected_rebuild():
        raise AssertionError("current SQLite get must not reparse sprint files")

    monkeypatch.setattr(pf.store, "_ticket_index_records", unexpected_rebuild)
    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.name == "Indexed ticket"
    assert loaded.priority == "high"


def test_summary_api_pages_and_filters_in_sqlite_without_full_list(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_tickets_bulk(
        [
            {
                "name": f"Ticket {number}",
                "priority": "high" if number % 2 else "normal",
            }
            for number in range(10)
        ]
    )
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    def unexpected_list(**_filters):
        raise AssertionError("summary page must be served by SQLite")

    monkeypatch.setattr(pf, "list_tickets", unexpected_list)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)
    response = client.get(
        "/tickets",
        params={
            "sprint": "current",
            "priority": "high",
            "offset": 1,
            "limit": 2,
            "view": "summary",
        },
    )

    assert response.status_code == 200
    assert [ticket["name"] for ticket in response.json()] == ["Ticket 3", "Ticket 5"]
    assert response.headers["X-Total-Count"] == "5"
    assert response.headers["X-Result-Count"] == "2"


def test_full_and_operational_api_views_use_sqlite_without_model_cache(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Indexed full payload", description="details")
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(
        pf,
        "list_tickets",
        lambda **_filters: (_ for _ in ()).throw(
            AssertionError("indexed list must not materialize ticket models")
        ),
    )
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)

    full = client.get("/tickets?sprint=all&limit=5000&view=full")
    operational = client.get("/tickets?sprint=all&limit=5000&view=operational")

    assert full.status_code == 200
    assert full.json()[0]["id"] == ticket.id
    assert full.json()[0]["description"] == ticket.description
    assert operational.status_code == 200
    assert operational.json()[0]["id"] == ticket.id
    assert "history" not in operational.json()[0]


def test_full_api_requires_pagination_before_materializing_oversized_page(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    for number in range(2):
        pf.create_ticket(
            name=f"Large ticket {number}",
            description="ą" * (128 * 1024),
        )
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setenv("PLANFILE_TICKET_RESPONSE_MAX_BYTES", str(1024 * 1024))
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)

    rejected = client.get("/tickets?sprint=all&limit=5000&view=full")

    assert rejected.status_code == 413
    assert rejected.json()["detail"] == "ticket_response_too_large"
    assert rejected.json()["estimated_bytes"] > 1024 * 1024
    assert rejected.json()["recommended_limit"] == 1
    assert rejected.headers["X-Total-Count"] == "2"
    assert rejected.headers["X-Planfile-Recommended-Limit"] == "1"
    assert server._TICKET_LIST_RESPONSE_CACHE == {}
    assert client.get("/tickets?sprint=all&limit=1&view=full").status_code == 200


def test_concurrent_stale_index_reads_perform_one_rebuild(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Before concurrent rebuild")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "After concurrent rebuild"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)
    original_records = pf.store._ticket_index_records
    calls = 0
    calls_lock = threading.Lock()

    def counted_records():
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        return original_records()

    monkeypatch.setattr(pf.store, "_ticket_index_records", counted_records)
    with ThreadPoolExecutor(max_workers=8) as pool:
        loaded = list(pool.map(lambda _number: pf.get_ticket(ticket.id), range(8)))

    assert calls == 1
    assert {item.name for item in loaded if item is not None} == {
        "After concurrent rebuild"
    }


def test_index_source_contention_falls_back_without_rebuild_storm(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Durable during contention")
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()

    signature_calls = 0
    original_signature = pf.store._ticket_index_signature

    def changing_signature():
        nonlocal signature_calls
        signature_calls += 1
        return original_signature(), signature_calls

    monkeypatch.setattr(pf.store, "_ticket_index_signature", changing_signature)
    client = TestClient(server.app)

    first = client.get("/tickets?view=operational&limit=1000")
    second = client.get("/tickets?view=operational&limit=1000")
    single = client.get(f"/tickets/{ticket.id}")
    unbounded_full = client.get("/tickets?sprint=all&view=full&limit=1000")

    assert first.status_code == 200
    assert first.json()[0]["id"] == ticket.id
    assert second.status_code == 200
    assert second.json()[0]["id"] == ticket.id
    assert single.status_code == 200
    assert single.json()["id"] == ticket.id
    assert unbounded_full.status_code == 503
    assert unbounded_full.headers["Retry-After"] == "5"
    # Request threads may validate signatures, but never enumerate the full
    # durable archive to repair the disposable projection.
    assert signature_calls < 20


def test_stale_api_reads_do_not_rebuild_the_index(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before external edit")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "Durable exact result"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(
        pf.store,
        "_ticket_index_records",
        lambda: (_ for _ in ()).throw(AssertionError("request-triggered rebuild")),
    )
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)

    exact = client.get(f"/tickets/{ticket.id}")
    summary = client.get("/tickets?view=summary&limit=100")
    full_archive = client.get("/tickets?sprint=all&view=full&limit=100")

    assert exact.status_code == 200
    assert exact.json()["name"] == "Durable exact result"
    assert summary.status_code == 200
    assert summary.json()[0]["name"] == "Durable exact result"
    assert full_archive.status_code == 503
    assert pf.store.ticket_index_status()["current"] is False


def test_stale_archive_summary_uses_bounded_cached_projection(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Cached archive result")
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)
    query = "/tickets?sprint=all&view=summary&limit=100"
    assert client.get(query).status_code == 200

    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "New durable value"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)
    monkeypatch.setattr(
        pf.store,
        "_ticket_index_records",
        lambda: (_ for _ in ()).throw(AssertionError("request-triggered rebuild")),
    )

    stale = client.get(query)

    assert stale.status_code == 200
    assert stale.json()[0]["name"] == "Cached archive result"
    assert stale.headers["X-Planfile-Index-State"] == "stale"


def test_stale_archive_queue_reads_use_recent_index_without_query_cache(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Last known good queue item")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "New durable value"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(
        pf.store,
        "_ticket_index_records",
        lambda: (_ for _ in ()).throw(AssertionError("request-triggered rebuild")),
    )
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)

    summary = client.get(
        "/tickets?sprint=all&status=open&limit=1&view=summary"
    )
    operational = client.get(
        "/tickets?sprint=all&status=open&limit=1&view=operational"
    )

    assert summary.status_code == 200
    assert summary.json()[0]["name"] == "Last known good queue item"
    assert summary.headers["X-Planfile-Index-State"] == "stale"
    assert operational.status_code == 200
    assert operational.json()[0]["name"] == "Last known good queue item"
    assert operational.headers["X-Planfile-Index-State"] == "stale"
    assert pf.store.ticket_index_status()["current"] is False


def test_legacy_archive_dashboard_uses_recent_current_index_without_cache(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Last known good dashboard item")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "New durable value"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(
        pf,
        "list_tickets",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy request parsed durable sprint")
        ),
    )
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)

    response = client.get("/tickets?sprint=all")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Last known good dashboard item"
    assert response.headers["X-Planfile-View"] == "summary"
    assert response.headers["X-Planfile-Index-State"] == "stale"


def test_expired_stale_archive_index_remains_fail_closed(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Expired queue item")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "New durable value"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)
    with sqlite3.connect(pf.store._ticket_index_path) as connection:
        connection.execute(
            "UPDATE meta SET value='0' WHERE key='source_indexed_at_ns'"
        )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)

    response = client.get(
        "/tickets?sprint=all&status=open&limit=1&view=summary"
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "ticket_index_repair_pending"}


def test_future_dated_stale_archive_index_remains_fail_closed(tmp_path):
    index = SQLiteTicketIndex(tmp_path / "tickets.sqlite3")
    index.rebuild([], ("source", 1))
    with sqlite3.connect(index.path) as connection:
        connection.execute(
            "UPDATE meta SET value=? WHERE key='source_indexed_at_ns'",
            (str(time.time_ns() + 1_000_000_000),),
        )

    assert index.has_fresh_snapshot(300) is False


def test_concurrent_background_repairs_coalesce_to_one_rebuild(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Before maintenance")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "After maintenance"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    expected_signature = pf.store._ticket_index_signature()
    original_records = pf.store._ticket_index_records
    calls = 0
    calls_lock = threading.Lock()

    def counted_records():
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        return original_records()

    monkeypatch.setattr(pf.store, "_ticket_index_records", counted_records)
    with ThreadPoolExecutor(max_workers=6) as pool:
        reports = list(
            pool.map(
                lambda _number: server._repair_ticket_index_if_unchanged(
                    expected_signature
                ),
                range(6),
            )
        )

    assert calls == 1
    assert any(report.get("rebuilt") for report in reports)
    assert pf.get_ticket(ticket.id).name == "After maintenance"
    assert pf.store.ticket_index_status()["current"] is True


def test_external_yaml_edit_marks_index_stale_and_self_heals(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Before external edit")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "After external edit"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)

    assert pf.store.ticket_index_status()["current"] is False
    loaded = pf.get_ticket(ticket.id)
    assert loaded is not None and loaded.name == "After external edit"
    assert pf.store.ticket_index_status()["current"] is True


def test_store_mutation_updates_current_index_incrementally(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Mutable")
    pf.store.configure_ticket_index(True)

    pf.update_ticket(ticket.id, priority="critical")

    assert pf.store.ticket_index_status()["current"] is True
    monkeypatch.setattr(
        pf.store,
        "_ticket_index_records",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected full rebuild")),
    )
    assert pf.get_ticket(ticket.id).priority == "critical"
    assert pf.store.ticket_index_status()["current"] is True


def test_corrupt_sqlite_index_is_discarded_and_rebuilt(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Survives disposable index corruption")
    pf.store.configure_ticket_index(True)
    index_path = pf.store._ticket_index_path
    pf.store._sqlite_ticket_index().reset()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(b"not a sqlite database")

    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.name == "Survives disposable index corruption"
    assert pf.store.ticket_index_status()["current"] is True


def test_evidence_change_updates_index_incrementally(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Evidence indexed")
    pf.store.configure_ticket_index(True)

    projected, recorded = pf.append_ticket_evidence(
        ticket.id,
        idempotency_key="run-1",
        collection="checks",
        evidence={"status": "passed"},
        actor="test",
        reason="verification",
    )

    assert recorded is True and projected is not None
    assert pf.store.ticket_index_status()["current"] is True
    monkeypatch.setattr(
        pf.store,
        "_ticket_index_records",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected full rebuild")),
    )
    loaded = pf.get_ticket(ticket.id)
    assert loaded.outputs.result["checks"][0]["status"] == "passed"
    assert pf.store.ticket_index_status()["current"] is True


def test_sqlite_index_works_with_sharded_yaml(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    created = pf.create_tickets_bulk(
        [{"name": f"Sharded {number}"} for number in range(20)]
    )
    pf.store.migrate_to_sharded_yaml(shard_size=5)
    pf.store.configure_ticket_index(True)

    assert pf.get_ticket(created[-1].id).name == "Sharded 19"
    summaries, total = pf.store.indexed_ticket_summaries(
        sprint="current",
        filters={},
        offset=5,
        limit=3,
    )
    assert total == 20
    assert [item["name"] for item in summaries] == [
        "Sharded 5",
        "Sharded 6",
        "Sharded 7",
    ]


def test_storage_index_cli_lifecycle(tmp_path):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="CLI indexed")
    runner = CliRunner()

    enabled = runner.invoke(
        app,
        ["storage", "index-enable", "--project", str(tmp_path), "--json"],
    )
    status = runner.invoke(
        app,
        ["storage", "index-status", "--project", str(tmp_path), "--json"],
    )
    disabled = runner.invoke(
        app,
        ["storage", "index-disable", "--project", str(tmp_path)],
    )

    assert enabled.exit_code == 0
    assert json.loads(enabled.output)["tickets"] == 1
    assert status.exit_code == 0
    assert json.loads(status.output)["current"] is True
    assert disabled.exit_code == 0
    assert Planfile(str(tmp_path)).store.ticket_index_enabled() is False


def test_evidence_revision_matches_glob_and_stat_listing(tmp_path):
    pf = Planfile(str(tmp_path))
    evidence_dir = pf.store._evidence_dir
    assert pf.store._evidence_revision() == ()

    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "PLF-2.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
    (evidence_dir / "PLF-10.jsonl").write_text("", encoding="utf-8")
    (evidence_dir / ".hidden.jsonl").write_text("{}\n", encoding="utf-8")
    (evidence_dir / "notes.json").write_text("{}", encoding="utf-8")
    (evidence_dir / "nested.jsonl").mkdir()
    (evidence_dir / "dangling.jsonl").symlink_to(evidence_dir / "missing")

    expected = []
    for path in sorted(evidence_dir.glob("*.jsonl")):
        try:
            stat = path.stat()
        except OSError:
            continue
        expected.append((path.name, stat.st_mtime_ns, stat.st_size))

    assert pf.store._evidence_revision() == tuple(expected)
    assert [name for name, _, _ in expected] == [
        ".hidden.jsonl",
        "PLF-10.jsonl",
        "PLF-2.jsonl",
        "nested.jsonl",
    ]

    with (evidence_dir / "PLF-2.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"b": 2}\n')
    assert pf.store._evidence_revision() != tuple(expected)


def test_background_repair_does_not_block_lifecycle_write(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Completes during projection repair")
    pf.store.configure_ticket_index(True)
    pf.store._sqlite_ticket_index().reset()
    writer = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    signature = pf.store._ticket_index_signature()
    entered = threading.Event()
    resume = threading.Event()
    original_records = pf.store._ticket_index_records
    calls = 0

    def paused_records():
        nonlocal calls
        calls += 1
        records = list(original_records())
        if calls == 1:
            entered.set()
            assert resume.wait(5), "test did not release projection repair"
        return records

    monkeypatch.setattr(pf.store, "_ticket_index_records", paused_records)
    with ThreadPoolExecutor(max_workers=2) as pool:
        repair = pool.submit(server._repair_ticket_index_if_unchanged, signature)
        try:
            assert entered.wait(2), "projection repair did not start"
            write = pool.submit(writer.complete_ticket, ticket.id, result={"ok": True})
            completed = write.result(timeout=2)
            assert completed.status == "done"
        finally:
            resume.set()
        repair.result(timeout=3)

    assert calls == 2  # The first snapshot raced the durable lifecycle write.
    assert pf.store.ticket_index_status()["current"] is True
    assert pf.get_ticket(ticket.id).status == "done"
    assert pf.get_ticket(ticket.id).outputs.result == {"ok": True}


def test_background_repair_defers_when_candidate_sources_changed(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Candidate changed")
    pf.store.configure_ticket_index(True)
    signature = pf.store._ticket_index_signature()
    pf.update_ticket(ticket.id, priority="critical")
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    def unexpected_repair():
        raise AssertionError("outdated maintenance candidate must defer")

    monkeypatch.setattr(pf.store, "ensure_ticket_index", unexpected_repair)
    assert server._repair_ticket_index_if_unchanged(signature) == {
        "rebuilt": False, "deferred": True,
    }


def _routing_record(number, *, repository="semcod/planfile", issue=244,
                    status="open", state="ready", position=None):
    payload = {"id": f"PLF-{number}", "status": status,
               "execution": {"queue": "coding-agent", "state": state},
               "inputs": {"api_body": {"source": {
                   "repository": repository, "issue": issue, "revision": str(number)}}}}
    return {"id": payload["id"], "sprint": "current" if status != "done" else "history",
            "status": status, "priority": "normal", "source": None, "queue": "coding-agent",
            "created_at": None, "updated_at": None,
            "position": number if position is None else position,
            "ticket_json": json.dumps(payload), "summary_json": json.dumps({"id": payload["id"]})}


def test_intent_queries_bound_history_work_at_50000_records(tmp_path):
    index = SQLiteTicketIndex(tmp_path / "routing.sqlite3")
    index.rebuild((_routing_record(n, status="done" if n < 49900 else "open")
                   for n in range(50000)), ("routing", 1))
    with index._connect() as connection:
        plans = [connection.execute("EXPLAIN QUERY PLAN " + sql).fetchall() for sql in (
            "SELECT id, position FROM ticket_routes WHERE queue='coding-agent' AND state='ready' "
            "AND active=1 AND (position,id)>(-1,'') ORDER BY position,id LIMIT 10",
            "SELECT id, position FROM ticket_routes WHERE queue='coding-agent' AND state='ready' "
            "AND active=1 AND repository='semcod/planfile' AND (position,id)>(-1,'') "
            "ORDER BY position,id LIMIT 10",
            "SELECT id, position FROM ticket_routes WHERE repository='semcod/planfile' AND issue=244 "
            "AND (position,id)>(49000,'') ORDER BY position,id LIMIT 10",
        )]
        for plan in plans:
            details = " ".join(row["detail"] for row in plan)
            assert "SEARCH" in details and "SCAN" not in details and "TEMP B-TREE" not in details
    calls = []
    connect = index._connect

    def traced_connect():
        connection = connect()
        connection.set_trace_callback(calls.append)
        return connection

    index._connect = traced_connect
    first = index.queue_page("coding-agent", "ready", limit=10)
    assert [r["id"] for r in first] == [f"PLF-{n}" for n in range(49900, 49910)]
    second = index.queue_page("coding-agent", "ready", repository="SEMCOD/Planfile",
                              limit=10, after=(first[-1]["position"], first[-1]["id"]))
    assert second[0]["id"] == "PLF-49910"
    assert len([sql for sql in calls if "SELECT ticket_json" in sql]) == 20
    assert not any("COUNT(" in sql.upper() or "OFFSET" in sql.upper() for sql in calls)
    assert len(index.lookup_issue("semcod/planfile", 244, limit=3)) == 3
    assert index.lookup_issue("other/project", 244) == []
    assert index.get_ticket("missing") is None


def test_routing_upgrade_reopen_delete_and_same_position_cursor(tmp_path):
    index = SQLiteTicketIndex(tmp_path / "routing.sqlite3")
    records = [_routing_record(1, status="done", position=0),
               _routing_record(2, status="blocked", state="waiting_dependency", position=0),
               _routing_record(3, status="failed", state="failed", position=0)]
    index.rebuild(records, ("before",))
    with index._connect() as connection:
        connection.execute("DROP TABLE ticket_routes")
        connection.execute("DELETE FROM meta WHERE key='routes_version'")
    # Opening the old projection upgrades without changing source signature or payloads.
    index = SQLiteTicketIndex(index.path)
    assert index.is_current(("before",))
    assert index.queue_page("coding-agent", "ready") == []
    assert index.queue_page("coding-agent", "waiting_dependency")[0]["id"] == "PLF-2"
    assert index.queue_page("coding-agent", "failed")[0]["id"] == "PLF-3"
    first = index.lookup_issue("semcod/planfile", 244, limit=1)
    second = index.lookup_issue("semcod/planfile", 244, limit=1,
                                after=(first[0]["position"], first[0]["id"]))
    assert first[0]["id"] != second[0]["id"]
    index.apply(upserts=[_routing_record(1)], deletes=["PLF-2"], signature=("after",))
    assert index.queue_page("coding-agent", "ready")[0]["id"] == "PLF-1"
    assert {r["id"] for r in index.lookup_issue("semcod/planfile", 244)} == {"PLF-1", "PLF-3"}
    assert index.get_ticket("PLF-2") is None


def test_conflicting_issue_identity_is_not_routed(tmp_path):
    index = SQLiteTicketIndex(tmp_path / "routing.sqlite3")
    record = _routing_record(1)
    payload = json.loads(record["ticket_json"])
    payload["sync"] = {"github": {"repository": "other/repository", "issue": 244}}
    record["ticket_json"] = json.dumps(payload)
    index.rebuild([record], ("conflict",))
    assert index.lookup_issue("semcod/planfile", 244) == []
    assert index.lookup_issue("other/repository", 244) == []
    assert index.get_ticket("PLF-1") == payload


@contextmanager
def _held_index_writer(pf, monkeypatch):
    """Hold a real WAL writer while keeping test contention waits bounded."""
    original_connect = SQLiteTicketIndex._connect

    def short_wait(index):
        connection = original_connect(index)
        connection.execute("PRAGMA busy_timeout=10")
        return connection

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteTicketIndex, "_connect", short_wait)
        connection = sqlite3.connect(pf.store._ticket_index_path)
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        finally:
            connection.rollback()
            connection.close()


def _evidence(pf, ticket_id, key="receipt-1"):
    return pf.append_ticket_evidence(
        ticket_id, idempotency_key=key, collection="receipts", evidence={"verified": True},
        actor="bot:test", reason="Observed external result",
    )


@pytest.mark.parametrize("sharded", [False, True])
@pytest.mark.parametrize("operation", ["create", "bulk-create", "update", "delete", "bulk-delete", "move", "evidence"])
def test_committed_mutation_survives_real_index_writer_contention(
    tmp_path, monkeypatch, caplog, sharded, operation,
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    if sharded:
        pf.store.migrate_to_sharded_yaml(shard_size=5)
    pf.store.configure_ticket_index(True)
    before = pf.store._ticket_index_signature()

    with _held_index_writer(pf, monkeypatch):
        if operation == "create":
            ticket = pf.create_ticket(name="After")
        elif operation == "bulk-create":
            ticket = pf.create_tickets_bulk([{"name": "After"}])[0]
        elif operation == "update":
            assert pf.update_ticket(ticket.id, name="After").name == "After"
        elif operation == "delete":
            assert pf.store.delete_ticket(ticket.id)
        elif operation == "bulk-delete":
            assert pf.delete_tickets([ticket.id]) == ([ticket.id], [])
        elif operation == "move":
            assert pf.store.move_ticket(ticket.id, "backlog")
        else:
            updated, recorded = _evidence(pf, ticket.id)
            assert recorded and updated.outputs.result["receipts"][0]["verified"]
        assert "ticket_index_update_deferred" in caplog.text
        assert not pf.store._sqlite_ticket_index().is_current(pf.store._ticket_index_signature())
        assert pf.store._ticket_index_signature() != before
        with pytest.raises(TicketIndexContentionError, match="ticket_index_stale"):
            pf.store.require_current_ticket_index()
        # An exact read must observe authoritative files, without repairing
        # the locked disposable index or claiming its snapshot is current.
        current = pf.get_ticket(ticket.id, repair_index=False)
        if operation in ("delete", "bulk-delete"):
            assert current is None
        elif operation == "move":
            assert current.sprint == "backlog"
        elif operation == "evidence":
            assert current.outputs.result["receipts"][0]["verified"]
        else:
            assert current.name == "After"

    assert pf.store.ensure_ticket_index()["current"] is True
    assert pf.get_ticket(ticket.id, repair_index=False) == current
    # A later incremental edit must not bless a projection missing the first.
    pf.create_ticket(name="Unrelated later mutation")
    assert pf.get_ticket(ticket.id, repair_index=False) == current


@pytest.mark.parametrize("operation", ["update", "evidence", "input-required"])
def test_api_acknowledges_committed_write_during_index_contention(
    tmp_path, monkeypatch, operation,
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    with _held_index_writer(pf, monkeypatch):
        if operation == "update":
            response = client.post(f"/tickets/{ticket.id}/update-if-current", json={
                "name": "After", "expected_updated_at": str(ticket.updated_at),
            })
        elif operation == "evidence":
            payload = {"idempotency_key": "api-receipt", "collection": "receipts",
                       "evidence": {"verified": True}, "actor": "bot:test", "reason": "Observed"}
            response = client.post(f"/tickets/{ticket.id}/evidence", json=payload)
            replay = client.post(f"/tickets/{ticket.id}/evidence", json=payload)
            assert replay.status_code == 200 and replay.json()["deduplicated"]
            payload["evidence"] = {"verified": False}
            assert client.post(f"/tickets/{ticket.id}/evidence", json=payload).status_code == 409
        else:
            response = client.post(f"/tickets/{ticket.id}/input-required", json={
                "prompt": "Which runtime is admitted?", "actor": "bot:test", "reason": "Missing binding",
            })
        assert response.status_code == 200, response.text
        current = pf.get_ticket(ticket.id, repair_index=False)
        if operation == "update":
            assert current.name == "After"
            # A committed write's old CAS must not be replayed as fresh work.
            assert client.post(f"/tickets/{ticket.id}/update-if-current", json={
                "name": "Replay", "expected_updated_at": str(ticket.updated_at),
            }).status_code == 409
        elif operation == "evidence":
            assert response.json()["recorded"]
            assert len(current.outputs.result["receipts"]) == 1
        else:
            assert current.execution.state == "waiting_input"


@pytest.mark.parametrize("edit", ["history", "existing-evidence"])
def test_failed_index_update_invalidates_another_process_cached_signature(
    tmp_path, monkeypatch, edit,
):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before", sprint="backlog")
    _evidence(pf, ticket.id, "existing")
    pf.store.configure_ticket_index(True)
    code = '''
import json, sys
from pathlib import Path
import planfile
from planfile import Planfile
from planfile.core.store import TicketIndexContentionError
assert Path(planfile.__file__).resolve() == Path(sys.argv[3]).resolve()
store = Planfile(sys.argv[1]).store
store._ticket_index_signature_cache_seconds = lambda: 3600
store.require_current_ticket_index()
print("ready", flush=True)
sys.stdin.readline()
try:
    store.require_current_ticket_index()
except TicketIndexContentionError as exc:
    print(json.dumps({"state": str(exc), "name": store.get_ticket(sys.argv[2], repair_index=False).name}), flush=True)
else:
    raise AssertionError("another process served stale projection as current")
'''
    source_root = Path(__file__).resolve().parents[1]
    process = subprocess.Popen([sys.executable, "-u", "-c", code, str(tmp_path), ticket.id,
                                str(source_root / "planfile/__init__.py")],
                               cwd=source_root,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
    try:
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            assert ready.select(timeout=30), "reader failed to warm cache"
        assert process.stdout.readline().strip() == "ready", process.stderr.read()
        probe_before = pf.store._ticket_index_signature_cache_probe()
        with _held_index_writer(pf, monkeypatch):
            if edit == "history":
                pf.update_ticket(ticket.id, name="After")
            else:
                _evidence(pf, ticket.id, "second")
            probe_after = pf.store._ticket_index_signature_cache_probe()
            # Neither edit changes the old cheap probe; only the new token
            # prevents a worker with a warmed signature from returning stale.
            assert probe_before[:-1] == probe_after[:-1]
            assert probe_before[-1] != probe_after[-1]
            output, error = process.communicate("check\n", timeout=15)
            assert process.returncode == 0, error
            assert json.loads(output)["state"] == "ticket_index_stale"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=15)
    assert pf.store.ensure_ticket_index()["current"] is True


@pytest.mark.parametrize("message", ["disk I/O error", "no such table: tickets", "database disk image is malformed"])
def test_non_contention_index_errors_still_propagate(tmp_path, monkeypatch, message):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)

    def broken_apply(*args, **kwargs):
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(SQLiteTicketIndex, "apply", broken_apply)
    with pytest.raises(sqlite3.OperationalError, match=message):
        pf.update_ticket(ticket.id, name="After")
    assert pf.store._locate_ticket_source(ticket.id)[1]["name"] == "After"
    assert not pf.store._ticket_index_invalidation_path.exists()


def test_pre_write_sqlite_failure_preserves_authoritative_ticket(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)

    def unavailable_source(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(pf.store, "_write_yaml_atomic", unavailable_source)
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        pf.update_ticket(ticket.id, name="After")
    assert pf.store._locate_ticket_source(ticket.id)[1]["name"] == "Before"
    assert pf.store.require_current_ticket_index()["current"] is True
    assert not pf.store._ticket_index_invalidation_path.exists()
    with pytest.raises(TicketUpdatedAtConflictError):
        pf.update_ticket(ticket.id, name="Stale", expected_updated_at="2000-01-01T00:00:00Z")


def test_actual_sqlite_locked_error_defers_only_post_commit_index(tmp_path, monkeypatch):
    # SQLITE_LOCKED differs from SQLITE_BUSY: produce it with an unfinished
    # statement in SQLite itself, rather than relying on exception text.
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE held(value)")
    connection.execute("INSERT INTO held VALUES(1)")
    cursor = connection.execute("SELECT * FROM held")
    with pytest.raises(sqlite3.OperationalError) as captured:
        connection.execute("DROP TABLE held")
    cursor.close()
    connection.close()
    error = captured.value
    if hasattr(error, "sqlite_errorcode"):
        assert error.sqlite_errorcode & 0xFF == 6
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)

    def locked_apply(*args, **kwargs):
        raise error

    monkeypatch.setattr(SQLiteTicketIndex, "apply", locked_apply)
    assert pf.update_ticket(ticket.id, name="After").name == "After"
    assert pf.get_ticket(ticket.id, repair_index=False).name == "After"
    assert pf.store.ensure_ticket_index()["current"] is True


@pytest.mark.parametrize("code", [5 | (2 << 8), 6 | (1 << 8)])
def test_extended_contention_codes_are_classified_by_primary_code(tmp_path, monkeypatch, code):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    error = sqlite3.OperationalError("localized or version-specific description")
    error.sqlite_errorcode = code

    def fail_apply(*args, **kwargs):
        raise error

    monkeypatch.setattr(SQLiteTicketIndex, "apply", fail_apply)
    assert pf.update_ticket(ticket.id, name="After").name == "After"
    assert pf.store._ticket_index_invalidation_path.exists()


def test_non_contention_error_code_overrides_lock_like_message(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    error = sqlite3.OperationalError("database is locked")
    error.sqlite_errorcode = 10  # SQLITE_IOERR must never be suppressed.

    def fail_apply(*args, **kwargs):
        raise error

    monkeypatch.setattr(SQLiteTicketIndex, "apply", fail_apply)
    with pytest.raises(sqlite3.OperationalError):
        pf.update_ticket(ticket.id, name="After")
    assert not pf.store._ticket_index_invalidation_path.exists()


def test_failure_to_persist_invalidation_is_not_hidden(tmp_path, monkeypatch):
    from planfile.core import fastio

    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    original = fastio._atomic_write_text

    def no_marker(path, content):
        if path == pf.store._ticket_index_invalidation_path:
            raise OSError("invalidation filesystem unavailable")
        return original(path, content)

    monkeypatch.setattr(fastio, "_atomic_write_text", no_marker)
    with _held_index_writer(pf, monkeypatch):
        with pytest.raises(OSError, match="invalidation filesystem unavailable"):
            pf.update_ticket(ticket.id, name="After")
    assert pf.store._locate_ticket_source(ticket.id)[1]["name"] == "After"
