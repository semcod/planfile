from __future__ import annotations

import asyncio
import subprocess
import sys
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


def test_external_source_race_never_publishes_a_false_current_signature(tmp_path, monkeypatch):
    pf = setup_store(tmp_path)
    ticket = pf.create_ticket(name="Before")
    pf.store.configure_ticket_index(True)
    built = pf.store._ticket_index_signature()
    monkeypatch.setattr(pf.store, "_begin_index_mutation", lambda: False)
    pf.update_ticket(ticket.id, name="After")
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
    assert index_repair.reconcile_index(pf.store, pf.store._sqlite_ticket_index(), built) is None
    assert pf.store._sqlite_ticket_index().get_ticket(ticket.id)["name"] == "Before"
