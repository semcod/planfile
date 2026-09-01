from __future__ import annotations

import gc
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from planfile import Planfile
from planfile.api import server
from planfile.cli.commands import app
from planfile.core.fastio import mirror_path
from planfile.core.sqlite_index import SQLiteTicketIndex


def _disable_archive(pf: Planfile) -> None:
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    pf.store._write_config(config)


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
    assert full.json()[0]["description"] == "details"
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
