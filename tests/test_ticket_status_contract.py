"""The published status contract covers exactly the TicketStatus enum (ticket-214)."""
import json
from importlib import resources

from planfile.core.models.base import TicketStatus


def contract():
    return json.loads(resources.files("planfile").joinpath("schemas/ticket-status.v1.json").read_text())


def test_contract_lists_every_ticket_status_exactly_once():
    assert set(contract()["statuses"]) == {status.value for status in TicketStatus}


def test_every_status_has_a_declared_class_and_pending_flag():
    data = contract()
    assert data["schema"] == "planfile.ticket-status/v1"
    for name, entry in data["statuses"].items():
        assert entry["class"] in data["classes"], name
        assert isinstance(entry["pending"], bool), name
        assert entry["pending"] == (not entry["class"].startswith("terminal_")), name


def test_only_open_is_ready_and_stalled_work_is_pending():
    statuses = contract()["statuses"]
    assert [name for name, entry in statuses.items() if entry["class"] == "ready"] == ["open"]
    assert {name for name, entry in statuses.items() if entry["class"] == "stalled"} == {"blocked", "failed"}
