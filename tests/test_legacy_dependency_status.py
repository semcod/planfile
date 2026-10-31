from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from planfile import Planfile
from planfile.api import server
from planfile.core.models import Ticket, TicketStatus
from planfile.core.store import TicketIndexContentionError


def install_legacy_row(pf, *, execution=None):
    raw = {
        "id": "PLF-21505", "name": "Wait for admitted scope repair",
        "status": "waiting_dependency", "blocked_by": ["PLF-20363"],
        "execution": execution, "executor": None,
        "inputs": {"api_body": {"retained": True}},
    }
    with pf.store.mutation_lock():
        pf.store._write_yaml_atomic(pf.store._sprint_file("current"), {
            "sprint": {"id": "current", "tickets": {raw["id"]: raw}}
        })
    return raw


@pytest.mark.parametrize("execution", [
    None, {}, {"queue": "willman"},
    {"queue": "willman", "state": "waiting_dependency", "attempt": 2},
])
def test_legacy_wait_is_visible_without_mutating_source_or_becoming_runnable(
    tmp_path, execution
):
    pf = Planfile(str(tmp_path))
    raw = install_legacy_row(pf, execution=execution)
    original = deepcopy(raw)
    path = pf.store._sprint_file("current")
    before = path.read_bytes()
    ticket = pf.store._ticket_from_data(raw)
    assert raw == original
    assert ticket.status is TicketStatus.open
    assert ticket.execution.state == "waiting_dependency"
    assert ticket.execution.queue == (execution or {}).get("queue", "default")
    assert ticket.execution.attempt == (execution or {}).get("attempt", 0)
    assert ticket.blocked_by == ["PLF-20363"]
    assert ticket.inputs.api_body == {"retained": True}
    assert ticket.executor is None and ticket.contract_version is None
    assert pf.get_ticket(ticket.id).id == ticket.id
    assert [row.id for row in pf.list_tickets()] == [ticket.id]
    # Even once the dependency is satisfied, the projected wait must not turn
    # into an implicitly admitted pending/ready execution.
    dependency = Ticket(id="PLF-20363", name="Satisfied dependency", status="done")
    assert pf.runnability_skip_reason(
        ticket, ticket_by_id={ticket.id: ticket, dependency.id: dependency}
    ) == "exec_state:waiting_dependency"
    assert pf.next_ticket() is None
    assert path.read_bytes() == before


@pytest.mark.parametrize("execution", [
    {"state": "done"}, {"state": "completed"}, {"state": "running"},
    {"state": "failed"}, ["malformed"],
])
def test_conflicting_execution_state_is_not_reopened_or_overwritten(tmp_path, execution):
    pf = Planfile(str(tmp_path))
    raw = install_legacy_row(pf, execution=execution)
    original = deepcopy(raw)
    assert pf.store._ticket_from_data(raw) is None
    assert raw == original


@pytest.mark.parametrize("indexed", [False, True])
def test_api_and_index_keep_legacy_dependency_row_visible(tmp_path, monkeypatch, indexed):
    pf = Planfile(str(tmp_path))
    raw = install_legacy_row(pf)
    before = pf.store._sprint_file("current").read_bytes()
    if indexed:
        assert pf.store.configure_ticket_index(True)["tickets"] == 1
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)
    point = client.get("/tickets/" + raw["id"])
    assert point.status_code == 200
    for view in ["full", "summary", "operational"]:
        listed = client.get("/tickets", params={
            "sprint": "all" if indexed else "current", "view": view, "limit": 100,
        })
        assert listed.status_code == 200, listed.text
        assert [row["id"] for row in listed.json()] == [raw["id"]]
        assert listed.json()[0]["status"] == "open"
        assert listed.json()[0]["execution"]["state"] == "waiting_dependency"
    assert point.json()["blocked_by"] == ["PLF-20363"]
    if indexed:
        assert pf.store.ticket_index_status()["current"] is True
        payload = pf.store._sqlite_ticket_index().get_ticket(raw["id"])
        assert payload["status"] == "open"
        assert payload["execution"]["state"] == "waiting_dependency"
    assert pf.store._sprint_file("current").read_bytes() == before


def test_command_model_still_rejects_noncanonical_dependency_status():
    with pytest.raises(ValidationError):
        Ticket(id="PLF-1", name="Strict command", status="waiting_dependency")


def test_current_old_generation_index_is_rebuilt_without_source_mutation(tmp_path):
    pf = Planfile(str(tmp_path))
    raw = install_legacy_row(pf)
    path = pf.store._sprint_file("current")
    before = path.read_bytes()
    config = pf.store._read_config()
    config["storage"]["index"] = "sqlite"
    pf.store._write_config(config)
    # The previous parser omitted this row but could still mark its source
    # signature current. Merely updating the parser must invalidate that DB.
    old_signature = pf.store._ticket_index_signature()[:-1]
    index = pf.store._sqlite_ticket_index()
    index.rebuild([], old_signature)
    assert index.is_current(old_signature)
    with pytest.raises(TicketIndexContentionError, match="stale"):
        pf.store.require_current_ticket_index()
    report = pf.store.ensure_ticket_index()
    assert report["rebuilt"] is True and report["current"] is True
    assert report["tickets"] == 1
    assert index.get_ticket(raw["id"])["execution"]["state"] == "waiting_dependency"
    assert path.read_bytes() == before
