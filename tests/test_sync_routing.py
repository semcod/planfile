from __future__ import annotations

from planfile.cli.groups.sync.core import _load_tickets_for_sync
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
    assert ticket["id"] == "ONEDEV-11"
    assert ticket["sprint"] == "backlog"
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
    assert ticket["id"] == "ONEDEV-11"
    assert ticket["sprint"] == "backlog"
    assert ticket["name"] == "Current title"
    assert ticket["description"] == "current evidence"
    assert ticket["sync"]["onedev"]["id"] == "11"
    assert ticket["sync"]["github"]["id"] == "42"


class FakeSyncStore:
    def is_initialized(self):
        return True

    def _all_sprint_ids(self):
        return ["current", "history-2026-09-14", "backlog"]

    def load_sprint(self, sprint_id):
        tickets = {
            "current": {
                "PLF-001": {"name": "active", "integration": ["github"]},
            },
            "history-2026-09-14": {
                "PLF-002": {
                    "name": "resolved",
                    "status": "done",
                    "integration": ["github"],
                    "sync": {"github": {"id": "42"}},
                },
            },
            "backlog": {
                "PLF-003": {"name": "local only", "integration": ["markdown"]},
            },
        }
        return {"tickets": tickets[sprint_id]}


def test_sync_loads_mapped_history_tickets_for_external_completion():
    tickets, source, _, _ = _load_tickets_for_sync(FakeSyncStore(), ".", "github")

    assert source == ".planfile/ structure"
    assert [ticket_id for ticket_id, _ in tickets] == ["PLF-001", "PLF-002"]
    assert tickets[1][1]["status"] == "done"


def test_github_label_update_is_idempotent_and_does_not_mutate_ticket_labels():
    from types import SimpleNamespace

    from planfile.sync.github import GitHubBackend

    class FakeRepo:
        def get_labels(self):
            return [SimpleNamespace(name="planfile"), SimpleNamespace(name="managed")]

        def create_label(self, **kwargs):
            raise AssertionError(f"unexpected label creation: {kwargs}")

    class FakeIssue:
        def __init__(self):
            self.labels = [SimpleNamespace(name="priority: high"), SimpleNamespace(name="legacy")]
            self.set_calls = []

        def set_labels(self, *labels):
            self.set_calls.append(labels)
            self.labels = [SimpleNamespace(name=label) for label in labels]

    backend = GitHubBackend.__new__(GitHubBackend)
    backend.repo = FakeRepo()
    issue = FakeIssue()
    ticket_labels = ["regression", "priority: high", "regression"]

    backend._update_labels(issue, ticket_labels, "high")
    backend._update_labels(issue, ticket_labels, "high")

    expected = ("regression", "priority-high", "planfile", "managed")
    assert ticket_labels == ["regression", "priority: high", "regression"]
    assert issue.set_calls == [expected, expected]
