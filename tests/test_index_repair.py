from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from types import SimpleNamespace

import pytest

from planfile import Planfile
from planfile.api import server
from planfile.core import index_repair
from planfile.core.store import TicketIndexContentionError


def setup_store(tmp_path):
    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    pf.store._write_config(config)
    return pf


def test_maintenance_repairs_even_when_every_observation_has_a_new_signature(monkeypatch):
    observations = 0
    repairs = []

    async def writer_tick(_interval):
        nonlocal observations
        observations += 1
        if observations == 3:
            raise asyncio.CancelledError

    store = SimpleNamespace(
        ticket_index_enabled=lambda: True,
        _ticket_index_signature=lambda: (observations,),
        _sqlite_ticket_index=lambda: SimpleNamespace(is_current=lambda _signature: False),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: SimpleNamespace(store=store))
    monkeypatch.setattr(server, "_repair_ticket_index", lambda: repairs.append(observations))
    monkeypatch.setattr(asyncio, "sleep", writer_tick)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server._maintain_ticket_index())
    assert repairs == [1, 2]


def test_maintenance_reuses_locator_observed_while_index_is_current(tmp_path, monkeypatch):
    pf = setup_store(tmp_path)
    active = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    observed = pf.store._ticket_index_signature()
    expected = index_repair.capture_locator_snapshot(pf.store, observed)
    assert expected is not None
    ticks = 0
    repairs = []

    async def next_tick(_interval):
        nonlocal ticks
        ticks += 1
        if ticks == 2:
            monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
            pf.update_ticket(active.id, name="After")
        if ticks == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(asyncio, "sleep", next_tick)
    monkeypatch.setattr(server, "_repair_ticket_index",
                        lambda *, locator_snapshot: repairs.append(locator_snapshot))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server._maintain_ticket_index())
    assert repairs == [expected]


@pytest.mark.parametrize("sharded", [False, True])
def test_rebuild_converges_when_an_independent_process_writes_during_every_scan(
    tmp_path, monkeypatch, sharded
):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before scan")
    if sharded:
        pf.store.migrate_to_sharded_yaml(shard_size=2)
    pf.store.configure_ticket_index(True)
    pf.store._sqlite_ticket_index().reset()
    original = pf.store._ticket_index_records
    scans = 0

    def concurrent_records():
        nonlocal scans
        scans += 1
        records = list(original())
        # This independent process must finish while the full SQLite scan
        # transaction remains open, proving it does not need the writer lock.
        subprocess.run(
            [sys.executable, "-c", """
import sys
from planfile import Planfile
pf = Planfile(sys.argv[1])
ticket_id = sys.argv[2]
pf.update_ticket(ticket_id, name='Concurrent canonical update')
pf.create_ticket(name='Concurrent new ticket')
pf.store.append_ticket_evidence(ticket_id, idempotency_key='during-scan',
 collection='scan_evidence', evidence={'ok': True},
 reason='independent writer during rebuild', actor='test:writer')
""", str(tmp_path), ticket.id],
            check=True, capture_output=True, text=True, timeout=10,
        )
        yield from records

    monkeypatch.setattr(pf.store, "_ticket_index_records", concurrent_records)
    result = pf.store.ensure_ticket_index()
    assert scans == 1
    assert result["current"] is True
    assert result["tickets"] == 2
    assert result["reconciled"] == 2
    loaded = pf.store._sqlite_ticket_index().get_ticket(ticket.id)
    assert loaded["name"] == "Concurrent canonical update"
    assert loaded["outputs"]["result"]["scan_evidence"][0]["ok"] is True
    writer = Planfile(str(tmp_path))
    writer.update_ticket(ticket.id, priority="critical")
    assert pf.store.ticket_index_status()["current"] is True
    assert pf.store._sqlite_ticket_index().get_ticket(ticket.id)["priority"] == "critical"


def test_evidence_only_drift_is_reconciled_without_loading_unchanged_archive(
    tmp_path, monkeypatch
):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Active")
    pf.create_ticket(name="Historical", sprint="history")
    pf.store.configure_ticket_index(True)
    built = pf.store._ticket_index_signature()
    # Canonical evidence changes while a stale scan is being finalized.
    with pf.store.mutation_lock():
        pf.store._append_ticket_evidence_event(ticket.id, {
            "idempotency_key": "evidence-only", "collection": "proof",
            "evidence": {"fresh": True},
        })
    read = index_repair.read_yaml_fast

    def bounded_read(path):
        assert path.stem != "history", "finalization scanned unchanged history"
        return read(path)

    monkeypatch.setattr(index_repair, "read_yaml_fast", bounded_read)
    result = index_repair.reconcile_index(pf.store, pf.store._sqlite_ticket_index(), built)
    assert result["current"] is True
    assert result["reconciled"] == 1
    payload = pf.store._sqlite_ticket_index().get_ticket(ticket.id)
    assert payload["outputs"]["result"]["proof"][0]["fresh"] is True


@pytest.mark.parametrize("budget", ["bytes", "tickets", "time", "locator"])
def test_unbounded_or_ambiguous_finalization_keeps_index_stale(tmp_path, monkeypatch, budget):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    built = pf.store._ticket_index_signature()
    # Avoid the normal incremental apply: this stands for the stale rebuild
    # having already committed its pre-mutation snapshot.
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    pf.update_ticket(ticket.id, name="After")
    if budget == "bytes":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_BYTES", 1)
    elif budget == "tickets":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_TICKETS", 0)
    elif budget == "time":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_SECONDS", -1)
    else:
        pf.store._history_locations_path.write_text("{}\n")
    assert index_repair.reconcile_index(pf.store, index, built) is None
    assert index.get_ticket(ticket.id)["name"] == "Before"
    with pytest.raises(TicketIndexContentionError, match="stale"):
        pf.store.require_current_ticket_index()


def test_removed_source_ticket_does_not_survive_finalization(tmp_path, monkeypatch):
    from planfile.core.fastio import read_yaml_fast

    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Will be removed")
    pf.store.configure_ticket_index(True)
    built = pf.store._ticket_index_signature()
    with pf.store.mutation_lock():
        path = pf.store._sprint_file("current")
        data = read_yaml_fast(path)
        del data["sprint"]["tickets"][ticket.id]
        pf.store._write_yaml_atomic(path, data)
    result = index_repair.reconcile_index(pf.store, pf.store._sqlite_ticket_index(), built)
    assert result["current"] is True
    assert result["tickets"] == 0
    assert pf.store._sqlite_ticket_index().get_ticket(ticket.id) is None


@pytest.mark.parametrize("stored", [False, True])
def test_external_source_race_never_publishes_a_false_current_signature(tmp_path, monkeypatch, stored):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    built = pf.store._ticket_index_signature()
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    pf.update_ticket(ticket.id, name="After")
    pf.store._ticket_index_invalidation_path.write_text("b" * 32)
    original = pf.store._ticket_index_signature
    calls = 0

    def racing_signature():
        nonlocal calls
        calls += 1
        signature = original()
        if calls > 1:
            return (*signature[:3], "external-editor")
        return signature

    monkeypatch.setattr(pf.store, "_ticket_index_signature", racing_signature)
    baseline = None if stored else built
    assert index_repair.reconcile_index(pf.store, pf.store._sqlite_ticket_index(), baseline) is None
    assert calls >= 2
    assert pf.store._sqlite_ticket_index().get_ticket(ticket.id)["name"] == "Before"


@pytest.mark.parametrize("sharded", [False, True])
@pytest.mark.parametrize("return_to_current", [False, True])
def test_rebuild_converges_across_independent_archive_locator_moves(
    tmp_path, monkeypatch, sharded, return_to_current
):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before relocation")
    if return_to_current:
        assert pf.store.move_ticket(ticket.id, "history-2026-10-31")
    if sharded:
        pf.store.migrate_to_sharded_yaml(shard_size=2)
    pf.store.configure_ticket_index(True)
    pf.store._sqlite_ticket_index().reset()
    original = pf.store._ticket_index_records
    scans = 0
    destination = "current" if return_to_current else "history-2026-10-31"

    def records():
        nonlocal scans
        scans += 1
        before = list(original())
        subprocess.run([
            sys.executable, "-c", """
import sys
from planfile import Planfile
pf = Planfile(sys.argv[1])
assert pf.store.move_ticket(sys.argv[2], sys.argv[3])
pf.update_ticket(sys.argv[2], name='Canonical relocated payload')
""", str(tmp_path), ticket.id, destination,
        ], check=True, capture_output=True, text=True, timeout=10)
        yield from before

    monkeypatch.setattr(pf.store, "_ticket_index_records", records)
    report = pf.store.ensure_ticket_index()
    assert scans == 1 and report["current"] and report["tickets"] == 1
    payload = pf.store._sqlite_ticket_index().get_ticket(ticket.id)
    assert payload["name"] == "Canonical relocated payload"
    assert payload["sprint"] == destination
    assert pf.store.get_ticket(ticket.id, repair_index=False).name == payload["name"]


@pytest.mark.parametrize("remove_mapping", [False, True])
def test_locator_only_delta_reselects_canonical_duplicate_without_archive_scan(
    tmp_path, monkeypatch, remove_mapping
):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="First history", sprint="history-a")
    raw = ticket.model_dump(mode="json", exclude_none=True)
    raw.update(name="Preferred history", sprint="history-b")
    pf.store._write_yaml_atomic(pf.store._sprint_file("history-b"), {
        "sprint": {"id": "history-b", "tickets": {ticket.id: raw}},
    })
    initial = "history-b" if remove_mapping else "history-a"
    with pf.store.mutation_lock():
        pf.store._record_history_locations_unlocked({ticket.id: initial})
    pf.store.configure_ticket_index(True)
    built = pf.store._ticket_index_signature()
    baseline = index_repair.capture_locator_snapshot(pf.store, built)
    assert baseline is not None
    locations = {} if remove_mapping else {ticket.id: "history-b"}
    with pf.store.mutation_lock():
        pf.store._write_yaml_atomic(pf.store._history_locations_path, {"tickets": locations})
    expected = pf.store.get_ticket(ticket.id, repair_index=False)
    read = index_repair.read_yaml_fast

    def bounded_read(path):
        assert path.stem in {"current", "backlog", expected.sprint}, "scanned unrelated history"
        return read(path)

    monkeypatch.setattr(index_repair, "read_yaml_fast", bounded_read)
    report = index_repair.reconcile_index(
        pf.store, pf.store._sqlite_ticket_index(), built, locator_snapshot=baseline,
    )
    assert report["current"] and report["tickets"] == 1 and report["reconciled"] == 1
    actual = pf.store._sqlite_ticket_index().get_ticket(ticket.id)
    assert (actual["name"], actual["sprint"]) == (expected.name, expected.sprint)


@pytest.mark.parametrize("failure", ["bytes", "time", "shape", "race", "signature"])
def test_locator_baseline_is_bounded_and_generation_matched(tmp_path, monkeypatch, failure):
    pf = setup_store(tmp_path)
    path = pf.store._history_locations_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("tickets: {PLF-1: history-a}\n")
    if failure == "shape":
        path.write_text("tickets: {PLF-1: ../outside}\n")
    built = pf.store._ticket_index_signature()
    if failure == "bytes":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_BYTES", 1)
    elif failure == "time":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_SECONDS", -1)
    elif failure == "signature":
        built = (*built[:2], None, *built[3:])
    elif failure == "race":
        load = index_repair.load_yaml_text

        def replace_after_read(text):
            path.write_text("tickets: {PLF-1: history-different}\n")
            return load(text)

        monkeypatch.setattr(index_repair, "load_yaml_text", replace_after_read)
    assert index_repair.capture_locator_snapshot(pf.store, built) is None


@pytest.mark.parametrize("failure", ["tickets", "bytes", "time", "race"])
def test_locator_delta_retains_budgets_and_external_race_refusal(
    tmp_path, monkeypatch, failure
):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    built = pf.store._ticket_index_signature()
    baseline = index_repair.capture_locator_snapshot(pf.store, built)
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    assert pf.store.move_ticket(ticket.id, "history-new")
    if failure == "tickets":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_TICKETS", 0)
    elif failure == "bytes":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_BYTES", 1)
    elif failure == "time":
        monkeypatch.setattr(index_repair, "MAX_REPAIR_SECONDS", -1)
    else:
        signature = pf.store._ticket_index_signature
        calls = 0

        def external_signature():
            nonlocal calls
            calls += 1
            current = signature()
            return current if calls == 1 else (*current[:3], "external-editor")

        monkeypatch.setattr(pf.store, "_ticket_index_signature", external_signature)
    assert index_repair.reconcile_index(
        pf.store, pf.store._sqlite_ticket_index(), built, locator_snapshot=baseline,
    ) is None
    assert pf.store._sqlite_ticket_index().get_ticket(ticket.id)["sprint"] == "current"


@pytest.mark.parametrize("change", ["update", "delete", "evidence"])
def test_background_repairs_stored_generation_without_archive_scan(tmp_path, monkeypatch, change):
    pf = setup_store(tmp_path)
    old = pf.create_ticket(name="Cold history", sprint="history-old")
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    if change == "delete":
        pf.store.delete_ticket(ticket.id)
    elif change == "update":
        pf.update_ticket(ticket.id, name="After")
    else:
        pf.store.append_ticket_evidence(ticket.id, idempotency_key="proof", collection="checks",
                                        evidence={"passed": True}, actor="test", reason="record outcome")
    pf.store._ticket_index_invalidation_path.write_text("b" * 32)
    with pytest.raises(TicketIndexContentionError):
        pf.store.require_current_ticket_index()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(pf.store, "_ticket_index_records", lambda: pytest.fail("full archive scan"))
    result = server._repair_ticket_index()
    assert result["current"] and result["reconciled"] == 1
    assert index.get_ticket(old.id)["name"] == "Cold history"
    row = index.get_ticket(ticket.id)
    if change == "delete":
        assert row is None
    elif change == "update":
        assert row["name"] == "After"
    else:
        assert row["outputs"]["result"]["checks"][0]["passed"]
    assert pf.store.require_current_ticket_index()["current"]


@pytest.mark.parametrize("token", [None, "c" * 32])
def test_background_repairs_one_changed_sprint_without_a_new_token(tmp_path, monkeypatch, token):
    pf = setup_store(tmp_path)
    cold = pf.create_ticket(name="Unchanged archive ticket", sprint="history-old")
    ticket = pf.create_ticket(name="Before")
    if token is not None:
        pf.store._ticket_index_invalidation_path.parent.mkdir(exist_ok=True, parents=True)
        pf.store._ticket_index_invalidation_path.write_text(token)
    pf.store.configure_ticket_index(True)
    before = pf.store._ticket_index_signature()
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    pf.update_ticket(ticket.id, name="Changed current sprint")
    after = pf.store._ticket_index_signature()
    assert before[0] != after[0] and before[1:] == after[1:]

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(pf.store, "_ticket_index_records", lambda: pytest.fail("full archive scan"))
    result = server._repair_ticket_index()
    index = pf.store._sqlite_ticket_index()
    assert result["current"] and result["reconciled"] == 1
    assert index.get_ticket(cold.id)["name"] == "Unchanged archive ticket"
    assert index.get_ticket(ticket.id)["name"] == "Changed current sprint"


@pytest.mark.parametrize("damage", [
    "invalid_json", "wrong_projection", "invalid_stamp", "unknown_source",
    "duplicate_journal", "invalid_token", "token_only", "schema", "locator",
    "ticket_budget", "byte_budget", "time_budget",
])
def test_background_falls_back_for_unknown_generations(tmp_path, monkeypatch, damage):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before")
    pf.store.append_ticket_evidence(ticket.id, idempotency_key="seed", collection="checks",
                                    evidence={"ok": True}, actor="test", reason="seed journal")
    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    pf.update_ticket(ticket.id, name="After")
    pf.store._ticket_index_invalidation_path.write_text("b" * 32)
    with index._connection() as con:
        sig = json.loads(con.execute("SELECT value FROM meta WHERE key='source_signature'").fetchone()[0])
        if damage == "wrong_projection":
            sig[4] = "old-version"
        elif damage == "invalid_stamp":
            sig[0][0][-1] = False
        elif damage == "unknown_source":
            sig[0][0][1] = "/unknown/sprint.yaml"
        elif damage == "duplicate_journal":
            sig[1].append(sig[1][0])
        elif damage == "invalid_token":
            sig[3] = []
        elif damage == "token_only":
            sig = json.loads(index.serialize_signature(pf.store._ticket_index_signature()))
            sig[3] = "a" * 32
        elif damage == "schema":
            con.execute("UPDATE meta SET value='future' WHERE key='schema_version'")
        elif damage == "locator":
            sig[2] = [1, 0]
        elif damage == "ticket_budget":
            monkeypatch.setattr(index_repair, "MAX_REPAIR_TICKETS", 0)
        elif damage == "byte_budget":
            monkeypatch.setattr(index_repair, "MAX_REPAIR_BYTES", 1)
        elif damage == "time_budget":
            monkeypatch.setattr(index_repair, "MAX_REPAIR_SECONDS", 0)
        value = "{" if damage == "invalid_json" else index.serialize_signature(sig)
        con.execute("UPDATE meta SET value=? WHERE key='source_signature'", (value,))
        con.commit()
    calls = []
    rebuild = pf.store._rebuild_ticket_index_unlocked

    def observed(index, *, force):
        calls.append(1)
        return rebuild(index, force=force)

    monkeypatch.setattr(pf.store, "_rebuild_ticket_index_unlocked", observed)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    assert server._repair_ticket_index()["current"]
    assert calls == [1]
    assert index.get_ticket(ticket.id)["name"] == "After"


def test_background_recovers_after_independent_writer_commits_while_sqlite_is_busy(tmp_path, monkeypatch):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before contention")
    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    with closing(sqlite3.connect(index.path)) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        subprocess.run(
            [sys.executable, "-c",
             "import sys; from planfile import Planfile; "
             "Planfile(sys.argv[1]).update_ticket(sys.argv[2], name='Durable update')",
             str(tmp_path), ticket.id],
            check=True, capture_output=True, text=True, timeout=45,
        )
        assert index.get_ticket(ticket.id)["name"] == "Before contention"
        with pytest.raises(TicketIndexContentionError):
            pf.store.require_current_ticket_index()

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setattr(pf.store, "_ticket_index_records", lambda: pytest.fail("full archive scan"))
    result = server._repair_ticket_index()
    assert result["current"] and result["reconciled"] == 1
    assert index.get_ticket(ticket.id)["name"] == "Durable update"


def test_multi_mb_current_sprint_reconciles_within_default_budget_and_restores_discovery_200(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient

    assert index_repair.MAX_REPAIR_SECONDS >= 8.0

    pf = setup_store(tmp_path)
    pf.create_ticket(name="Cold archive ticket", sprint="history-old")
    ticket = pf.create_ticket(
        name="Before slow current delta",
        execution={"queue": "coding-agent", "state": "ready"},
    )
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    pf.update_ticket(ticket.id, name="After slow current delta")

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    query = {"mode": "queue", "queue": "coding-agent", "state": "ready"}
    stale = client.get("/tickets/discovery", params=query)
    assert stale.status_code == 503
    assert stale.headers.get("Retry-After") == "2"

    now = 1000.0
    read = index_repair.read_yaml_fast

    def fake_monotonic():
        return now

    def slow_current_read(path):
        nonlocal now
        if path.stem == "current":
            now += 2.6
        return read(path)

    monkeypatch.setattr(index_repair.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(index_repair, "read_yaml_fast", slow_current_read)
    monkeypatch.setattr(pf.store, "_ticket_index_records", lambda: pytest.fail("full archive scan"))

    result = server._repair_ticket_index()
    assert result["current"] is True and result["reconciled"] == 1

    recovered = client.get("/tickets/discovery", params=query)
    assert recovered.status_code == 200
    assert any(
        row["id"] == ticket.id and row["name"] == "After slow current delta"
        for row in recovered.json()["tickets"]
    )


@pytest.mark.parametrize("new_daily_history", [False, True])
@pytest.mark.parametrize("sharded", [False, True])
def test_background_repairs_auto_archive_move_without_full_rebuild(
    tmp_path, monkeypatch, new_daily_history, sharded
):
    from fastapi.testclient import TestClient

    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["archive"]["enabled"] = True
    config["archive"]["max_current_tickets"] = 1
    config["archive"]["keep_recent_terminal"] = 0
    pf.store._write_config(config)

    cold = pf.create_ticket(name="Cold archive ticket", sprint="history-2026-10-01")
    if not new_daily_history:
        # Seed today's daily archive file so it already exists before rotation.
        pre_done = pf.create_ticket(name="Already archived today")
        pf.update_ticket(pre_done.id, status="done")
        pf.store.archive_completed(force=True)

    active = pf.create_ticket(
        name="Queued coding ticket",
        execution={"queue": "coding-agent", "state": "ready"},
    )
    completing = pf.create_ticket(name="Hourly scheduled ticket")
    removed_shard = None
    if sharded:
        pf.store.migrate_to_sharded_yaml(shard_size=1)
        removed_shard = pf.store._sharded_storage().shard_path("current", completing.id)
        assert removed_shard.is_file()
    pf.store.configure_ticket_index(True)
    assert pf.store.require_current_ticket_index()["current"]

    # Completing triggers _archive_completed_unlocked(), which rotates the ticket
    # into history-YYYY-MM-DD.yaml, updates history-locations.yaml, and leaves
    # the SQLite index stale across two sprints.
    pf.update_ticket(completing.id, status="done")
    if removed_shard is not None:
        assert not removed_shard.exists()
    with pytest.raises(TicketIndexContentionError, match="stale"):
        pf.store.require_current_ticket_index()

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    query = {"mode": "queue", "queue": "coding-agent", "state": "ready"}
    assert client.get("/tickets/discovery", params=query).status_code == 503

    monkeypatch.setattr(pf.store, "_ticket_index_records", lambda: pytest.fail("full archive scan"))
    result = server._repair_ticket_index()
    assert result["current"] is True
    assert result["reconciled"] >= 2

    index = pf.store._sqlite_ticket_index()
    assert index.get_ticket(cold.id)["name"] == "Cold archive ticket"
    archived_row = index.get_ticket(completing.id)
    assert archived_row["status"] == "done"
    assert archived_row["sprint"].startswith("history-")

    recovered = client.get("/tickets/discovery", params=query)
    assert recovered.status_code == 200
    assert any(row["id"] == active.id for row in recovered.json()["tickets"])


def test_background_rejects_removed_shard_with_unaccounted_ticket(tmp_path):
    from planfile.core.fastio import mirror_path

    pf = setup_store(tmp_path)
    pf.create_ticket(name="Cold history", sprint="history-2026-10-01")
    unaffected = pf.create_ticket(name="Must stay in current")
    completing = pf.create_ticket(name="Will move to history")
    pf.store.migrate_to_sharded_yaml(shard_size=100)
    storage = pf.store._sharded_storage()
    shard = storage.shard_path("current", completing.id)
    assert shard == storage.shard_path("current", unaffected.id)
    pf.store.configure_ticket_index(True)

    config = pf.store._read_config()
    config["archive"].update(enabled=True, max_current_tickets=1, keep_recent_terminal=0)
    pf.store._write_config(config)
    pf.update_ticket(completing.id, status="done")
    assert shard.is_file()
    # Model a separate deletion after the archive writer moved only the completed ticket.
    with pf.store.mutation_lock():
        shard.unlink()
        mirror_path(shard).unlink(missing_ok=True)

    index = pf.store._sqlite_ticket_index()
    assert index_repair._stored_baseline(index, pf.store._ticket_index_signature()) is not None
    assert index_repair.reconcile_index(pf.store, index) is None
    assert index.get_ticket(unaffected.id)["sprint"] == "current"
    with pytest.raises(TicketIndexContentionError, match="stale"):
        pf.store.require_current_ticket_index()


def test_background_rejects_out_of_scope_locator_change_from_stored_baseline(
    tmp_path, monkeypatch
):
    pf = setup_store(tmp_path)
    first = pf.create_ticket(name="History A copy", sprint="history-a")
    raw = first.model_dump(mode="json", exclude_none=True)
    raw.update(name="History B copy", sprint="history-b")
    pf.store._write_yaml_atomic(pf.store._sprint_file("history-b"), {
        "sprint": {"id": "history-b", "tickets": {first.id: raw}},
    })
    with pf.store.mutation_lock():
        pf.store._record_history_locations_unlocked({first.id: "history-a"})
    active = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)

    # Mutate current.yaml AND externally repoint an unrelated duplicate ticket
    # between two unchanged history sprints without touching either history file.
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    pf.update_ticket(active.id, name="After")
    with pf.store.mutation_lock():
        pf.store._record_history_locations_unlocked({first.id: "history-b"})

    rebuilds = []
    orig_rebuild = pf.store._rebuild_ticket_index_unlocked

    def tracked_rebuild(index, *, force):
        rebuilds.append(1)
        return orig_rebuild(index, force=force)

    monkeypatch.setattr(pf.store, "_rebuild_ticket_index_unlocked", tracked_rebuild)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    result = server._repair_ticket_index()
    assert result["current"] is True
    assert rebuilds == [1]
    assert pf.store._sqlite_ticket_index().get_ticket(first.id)["sprint"] == "history-b"


@pytest.mark.parametrize("sharded", [False, True])
@pytest.mark.parametrize("prefix", ["history", "archive"])
@pytest.mark.parametrize("locator_source", ["none", "memory", "persisted"])
def test_background_rebuilds_after_unrelated_locator_removal(
    tmp_path, monkeypatch, sharded, prefix, locator_source,
):
    pf = setup_store(tmp_path)
    earlier, preferred = f"{prefix}-a", f"{prefix}-b"
    first = pf.create_ticket(name="First history", sprint=earlier)
    raw = first.model_dump(mode="json", exclude_none=True)
    raw.update(name="Preferred history", sprint=preferred)
    pf.store._write_yaml_atomic(pf.store._sprint_file(preferred), {
        "sprint": {"id": preferred, "tickets": {first.id: raw}},
    })
    active = pf.create_ticket(name="Stay in current")
    completing = pf.create_ticket(name="Move to daily history")
    if sharded:
        pf.store.migrate_to_sharded_yaml(shard_size=1)
    with pf.store.mutation_lock():
        pf.store._move_history_location_unlocked(first.id, preferred)
    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    assert index.get_ticket(first.id)["sprint"] == preferred
    snapshot = None
    if locator_source != "none":
        signature = pf.store._ticket_index_signature()
        snapshot = index_repair.capture_locator_snapshot(pf.store, signature)
        assert snapshot is not None
        if locator_source == "persisted":
            assert index_repair.persist_locator_snapshot(index, signature, snapshot)
            snapshot = None

    config = pf.store._read_config()
    config["archive"].update(enabled=True, max_current_tickets=1, keep_recent_terminal=0)
    pf.store._write_config(config)
    pf.update_ticket(completing.id, status="done")
    with pf.store.mutation_lock():
        pf.store._move_history_location_unlocked(first.id, "current")
    assert pf.store._history_locations()[completing.id].startswith("history-")
    assert index_repair._stored_baseline(index, pf.store._ticket_index_signature()) is not None
    assert index_repair.reconcile_index(pf.store, index, locator_snapshot=snapshot) is None

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    result = server._repair_ticket_index(locator_snapshot=snapshot)
    assert result["current"] and "reconciled" not in result
    assert index.get_ticket(first.id)["sprint"] == earlier
    assert index.get_ticket(first.id)["name"] == first.name
    assert index.get_ticket(active.id)["sprint"] == "current"


@pytest.mark.parametrize("restart", [False, True])
def test_known_prior_locator_avoids_unrelated_archive_reads(
    tmp_path, monkeypatch, restart
):
    pf = setup_store(tmp_path)
    pf.create_ticket(name="Backlog item", sprint="backlog")
    pf.create_ticket(name="Legacy archive 07", sprint="archive-2026-07")
    pf.create_ticket(name="Legacy archive 08", sprint="archive-2026-08")
    tracked = pf.create_ticket(name="Mapped history", sprint="history-old")
    with pf.store.mutation_lock():
        pf.store._record_history_locations_unlocked({tracked.id: "history-old"})
    active = pf.create_ticket(name="Stay in current")
    completing = pf.create_ticket(name="Archive to daily history")

    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    assert pf.store.require_current_ticket_index()["current"]
    signature = pf.store._ticket_index_signature()
    snapshot = index_repair.capture_locator_snapshot(pf.store, signature)
    assert snapshot is not None and snapshot.locations[tracked.id] == "history-old"
    if restart:
        assert index_repair.persist_locator_snapshot(index, signature, snapshot)

    config = pf.store._read_config()
    config["archive"].update(enabled=True, max_current_tickets=1, keep_recent_terminal=0)
    pf.store._write_config(config)
    pf.update_ticket(completing.id, status="done")
    if restart:
        pf = Planfile(str(tmp_path))
        index = pf.store._sqlite_ticket_index()
        snapshot = None

    orig_read_yaml = index_repair.read_yaml_fast

    def forbid_legacy_archive_reads(path):
        if getattr(path, "stem", "") in {"backlog", "archive-2026-07", "archive-2026-08"}:
            raise AssertionError(f"untouched non-locator sprint read: {path}")
        return orig_read_yaml(path)

    def forbid_full_identity_scan(index):
        raise AssertionError("verified locator additions need only the affected ticket IDs")

    monkeypatch.setattr(index_repair, "read_yaml_fast", forbid_legacy_archive_reads)
    monkeypatch.setattr(index_repair, "_indexed_ticket_sprints", forbid_full_identity_scan)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    reconciled = server._repair_ticket_index(locator_snapshot=snapshot)
    assert reconciled is not None
    assert reconciled["current"] is True
    assert reconciled["reconciled"] >= 2
    assert index.get_ticket(active.id)["sprint"] == "current"
    assert index.get_ticket(completing.id)["sprint"].startswith("history-")


def test_repair_retains_locator_for_the_next_deferred_archive_move(tmp_path, monkeypatch):
    pf = setup_store(tmp_path)
    store = pf.store
    history = "history-2026-11-20"
    tracked = pf.create_ticket(name="Previously archived", sprint="history-old")
    with store.mutation_lock():
        store._record_history_locations_unlocked({tracked.id: "history-old"})
    first = pf.create_ticket(name="First move")
    second = pf.create_ticket(name="Second move")
    store.configure_ticket_index(True)
    signature = store._ticket_index_signature()
    snapshot = index_repair.capture_locator_snapshot(store, signature)
    assert snapshot is not None
    assert index_repair.persist_locator_snapshot(store._sqlite_ticket_index(), signature, snapshot)

    def forbid_full_scan(*args, **kwargs):
        pytest.fail("a verified locator addition must use bounded reconciliation")

    monkeypatch.setattr(index_repair, "_indexed_ticket_sprints", forbid_full_scan)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    for ticket in (first, second):
        with monkeypatch.context() as deferred:
            deferred.setattr(pf.store, "_begin_index_mutation", lambda: False)
            assert pf.store.move_ticket(ticket.id, history)
        pf = Planfile(str(tmp_path))
        monkeypatch.setattr(pf.store, "_rebuild_ticket_index_unlocked", forbid_full_scan)
        assert not pf.store.ticket_index_status()["current"]
        result = server._repair_ticket_index()
        assert result["current"] and result["reconciled"]
        assert pf.store._sqlite_ticket_index().get_ticket(ticket.id)["sprint"] == history


def test_locator_snapshot_cannot_overwrite_a_newer_index_generation(tmp_path):
    pf = setup_store(tmp_path)
    store = pf.store
    first = pf.create_ticket(name="First location", sprint="history-old")
    with store.mutation_lock():
        store._record_history_locations_unlocked({first.id: "history-old"})
    store.configure_ticket_index(True)
    index = store._sqlite_ticket_index()
    previous_signature = store._ticket_index_signature()
    previous = index_repair.capture_locator_snapshot(store, previous_signature)
    assert previous is not None
    assert index_repair.persist_locator_snapshot(index, previous_signature, previous)

    second = pf.create_ticket(name="Second location", sprint="history-new")
    with store.mutation_lock():
        store._record_history_locations_unlocked({second.id: "history-new"})
    store.ensure_ticket_index(force=True)
    signature = store._ticket_index_signature()
    current = index_repair.capture_locator_snapshot(store, signature)
    assert current is not None
    assert index_repair.persist_locator_snapshot(index, signature, current)
    assert not index_repair.persist_locator_snapshot(index, previous_signature, previous)
    restored = index_repair._restore_locator_snapshot(store, index, signature)
    assert restored and restored.locations == current.locations
    assert index_repair._restore_locator_snapshot(store, index, previous_signature) is None


def test_has_unmapped_earlier_copy_still_guards_custom_locator_backed_sprints():
    # A custom non-'history-' sprint that IS referenced in locations.values()
    # remains locator-eligible and still flags an earlier duplicate copy.
    indexed_sprints = {
        "PLF-1": "custom-arch",
        "PLF-2": "custom-arch",
        "PLF-3": "archive-2026-07",
    }
    locations = {"PLF-2": "custom-arch"}
    reads: list[str] = []

    def fake_tickets(sprint: str) -> dict:
        reads.append(sprint)
        return {"PLF-1": {"id": "PLF-1"}} if sprint == "backlog" else {}

    assert index_repair._has_unmapped_earlier_copy(
        indexed_sprints,
        locations,
        affected=set(),
        sprint_order=["current", "backlog", "archive-2026-07", "custom-arch"],
        tickets=fake_tickets,
    ) is True
    assert "backlog" in reads


def test_aborted_post_rebuild_reconcile_persists_built_locator_snapshot(
    tmp_path, monkeypatch
):
    pf = setup_store(tmp_path)
    pf.create_ticket(name="Backlog item", sprint="backlog")
    pf.create_ticket(name="Legacy archive", sprint="archive-2026-07")
    tracked = pf.create_ticket(name="Previously archived", sprint="history-old")
    with pf.store.mutation_lock():
        pf.store._record_history_locations_unlocked({tracked.id: "history-old"})
    active = pf.create_ticket(name="Stay in current")
    moving = pf.create_ticket(name="Move while rebuilding")

    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    built = pf.store._ticket_index_signature()
    built_snapshot = index_repair.capture_locator_snapshot(pf.store, built)
    assert built_snapshot is not None
    # Simulate a full rebuild that committed source_signature without a saved locator.
    assert index_repair._restore_locator_snapshot(pf.store, index, built) is None

    with monkeypatch.context() as deferred:
        deferred.setattr(pf.store, "_begin_index_mutation", lambda: False)
        assert pf.store.move_ticket(moving.id, "history-2026-11-21")

    with monkeypatch.context() as aborted:
        aborted.setattr(index_repair, "MAX_REPAIR_SECONDS", -1)
        assert index_repair.reconcile_index(
            pf.store, index, built, locator_snapshot=built_snapshot
        ) is None

    restored = index_repair._restore_locator_snapshot(pf.store, index, built)
    assert restored is not None
    assert restored.locations == built_snapshot.locations

    reopened = Planfile(str(tmp_path))

    def forbid_full_scan(*args, **kwargs):
        pytest.fail("persisted rebuilt locator must enable bounded stored-baseline repair")

    monkeypatch.setattr(index_repair, "_indexed_ticket_sprints", forbid_full_scan)
    monkeypatch.setattr(reopened.store, "_rebuild_ticket_index_unlocked", forbid_full_scan)
    monkeypatch.setattr(server, "get_planfile", lambda: reopened)
    result = server._repair_ticket_index()
    assert result["current"] is True
    assert result["reconciled"] >= 2
    assert reopened.store._sqlite_ticket_index().get_ticket(active.id)["sprint"] == "current"
    assert reopened.store._sqlite_ticket_index().get_ticket(moving.id)["sprint"] == "history-2026-11-21"


def test_repair_ticket_index_persists_locator_after_quiet_full_rebuild(
    tmp_path, monkeypatch
):
    pf = setup_store(tmp_path)
    pf.create_ticket(name="Backlog item", sprint="backlog")
    pf.create_ticket(name="Legacy archive", sprint="archive-2026-07")
    tracked = pf.create_ticket(name="Previously archived", sprint="history-old")
    with pf.store.mutation_lock():
        pf.store._record_history_locations_unlocked({tracked.id: "history-old"})
    pf.create_ticket(name="Stay in current")
    moving = pf.create_ticket(name="Archive after quiet rebuild")

    pf.store.configure_ticket_index(True)
    pf.store._sqlite_ticket_index().reset()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    rebuilt = server._repair_ticket_index()
    assert rebuilt["current"] is True
    sig = pf.store._ticket_index_signature()
    restored = index_repair._restore_locator_snapshot(
        pf.store, pf.store._sqlite_ticket_index(), sig
    )
    assert restored is not None
    assert restored.locations[tracked.id] == "history-old"

    with monkeypatch.context() as deferred:
        deferred.setattr(pf.store, "_begin_index_mutation", lambda: False)
        assert pf.store.move_ticket(moving.id, "history-2026-11-21")

    reopened = Planfile(str(tmp_path))

    def forbid_full_scan(*args, **kwargs):
        pytest.fail("quiet full rebuild must persist locator for next deferred archive move")

    monkeypatch.setattr(index_repair, "_indexed_ticket_sprints", forbid_full_scan)
    monkeypatch.setattr(reopened.store, "_rebuild_ticket_index_unlocked", forbid_full_scan)
    monkeypatch.setattr(server, "get_planfile", lambda: reopened)
    result = server._repair_ticket_index()
    assert result["current"] is True
    assert result["reconciled"] >= 2
    assert reopened.store._sqlite_ticket_index().get_ticket(moving.id)["sprint"] == "history-2026-11-21"


def test_persist_current_locator_snapshot_syncs_after_incremental_archive(
    tmp_path, monkeypatch
):
    pf = setup_store(tmp_path)
    pf.create_ticket(name="Backlog item", sprint="backlog")
    tracked = pf.create_ticket(name="Previously archived", sprint="history-old")
    with pf.store.mutation_lock():
        pf.store._record_history_locations_unlocked({tracked.id: "history-old"})
    first = pf.create_ticket(name="First archived")
    second = pf.create_ticket(name="Second archived")

    pf.store.configure_ticket_index(True)
    assert pf.store.move_ticket(first.id, "history-2026-11-21")
    assert pf.store.ticket_index_status()["current"] is True
    assert server._persist_current_locator_snapshot(pf.store) is True

    with monkeypatch.context() as deferred:
        deferred.setattr(pf.store, "_begin_index_mutation", lambda: False)
        assert pf.store.move_ticket(second.id, "history-2026-11-21")

    reopened = Planfile(str(tmp_path))

    def forbid_full_scan(*args, **kwargs):
        pytest.fail("synced locator after incremental archive must reconcile without full scan")

    monkeypatch.setattr(index_repair, "_indexed_ticket_sprints", forbid_full_scan)
    monkeypatch.setattr(reopened.store, "_rebuild_ticket_index_unlocked", forbid_full_scan)
    monkeypatch.setattr(server, "get_planfile", lambda: reopened)
    result = server._repair_ticket_index()
    assert result["current"] is True
    assert result["reconciled"] >= 2
    assert reopened.store._sqlite_ticket_index().get_ticket(second.id)["sprint"] == "history-2026-11-21"


def test_stored_baseline_reconcile_returns_current_without_full_rebuild_after_concurrent_writer(
    tmp_path, monkeypatch
):
    pf = setup_store(tmp_path)
    pf.create_ticket(name="Active ticket")
    pf.store.configure_ticket_index(True)
    index = pf.store._sqlite_ticket_index()
    assert pf.store.ticket_index_status()["current"] is True

    # Simulate a maintenance check observing a mid-commit mutation right before
    # the writer finishes index.apply() and releases store.mutation_lock().
    result = index_repair.reconcile_index(pf.store, index)
    assert result is not None
    assert result["current"] is True
    assert result["rebuilt"] is False


def test_repair_ticket_index_defers_instead_of_rebuilding_on_sqlite_contention(
    tmp_path, monkeypatch
):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before busy repair")
    pf.store.configure_ticket_index(True)
    with monkeypatch.context() as deferred:
        deferred.setattr(pf.store, "_begin_index_mutation", lambda: False)
        pf.update_ticket(ticket.id, name="After busy repair")

    def busy_reconcile(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    def forbid_rebuild(*args, **kwargs):
        pytest.fail("transient SQLite contention must defer instead of launching full rebuild")

    monkeypatch.setattr(index_repair, "reconcile_index", busy_reconcile)
    monkeypatch.setattr(pf.store, "_rebuild_ticket_index_unlocked", forbid_rebuild)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    with pytest.raises(TicketIndexContentionError, match="ticket_index_repair_busy"):
        server._repair_ticket_index()
