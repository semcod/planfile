from __future__ import annotations

from planfile.sync.base import TicketState
from planfile.sync.operations import (
    _extract_ticket_data,
    _import_new_ticket,
    _ticket_external_id,
    _update_local_ticket,
)


class FakeSyncState:
    def __init__(self):
        self.mapping = {}

    def get_remote_id(self, local_id):
        return self.mapping.get(local_id)

    def save_sync(self, mapping):
        self.mapping.update(mapping)


def test_onedev_import_routes_ticket_to_github_without_losing_evidence():
    backlog = {"tickets": {}}
    state = FakeSyncState()
    external = TicketState(
        id="11",
        key="subactor/doctor-agent#2",
        name="Doctor finding",
        description="full evidence",
        url="http://onedev/subactor/doctor-agent/~issues/2",
        status="open",
        labels=["onedev:subactor/doctor-agent"],
        metadata={"deduplication_key": "doctor:abc"},
    )

    imported = _import_new_ticket(
        backlog,
        _extract_ticket_data(external),
        "onedev",
        state,
        0,
        publish_to=["github"],
    )

    ticket = backlog["tickets"]["ONEDEV-11"]
    assert imported == 1
    assert ticket["name"] == "Doctor finding"
    assert ticket["description"] == "full evidence"
    assert ticket["integration"] == ["onedev", "github"]
    assert ticket["metadata"]["deduplication_key"] == "doctor:abc"
    assert ticket["sync"]["onedev"]["id"] == "11"


def test_backend_scoped_id_never_treats_onedev_id_as_github_issue_number():
    state = FakeSyncState()
    ticket = {
        "external_id": "11",
        "backend": "onedev",
        "sync": {"onedev": {"id": "11"}},
    }

    assert _ticket_external_id(ticket, "ONEDEV-11", "github", state) is None
    ticket["sync"]["github"] = {"id": "42"}
    assert _ticket_external_id(ticket, "ONEDEV-11", "github", state) == "42"


def test_onedev_refresh_updates_content_and_preserves_other_backend_reference():
    backlog = {
        "tickets": {
            "ONEDEV-11": {
                "name": "stale title",
                "description": "stale evidence",
                "sync": {"github": {"id": "42"}},
            }
        }
    }
    external = TicketState(
        id="11",
        key="subactor/doctor-agent#2",
        name="Current title",
        description="current evidence",
        url="http://onedev/subactor/doctor-agent/~issues/2",
        status="in_progress",
        labels=["onedev:subactor/doctor-agent"],
        metadata={"deduplication_key": "doctor:abc"},
    )

    updated = _update_local_ticket(
        {"tickets": {}},
        backlog,
        "ONEDEV-11",
        _extract_ticket_data(external),
        0,
        "onedev",
        ["github"],
    )

    ticket = backlog["tickets"]["ONEDEV-11"]
    assert updated == 1
    assert ticket["name"] == "Current title"
    assert ticket["description"] == "current evidence"
    assert ticket["sync"]["onedev"]["id"] == "11"
    assert ticket["sync"]["github"]["id"] == "42"
