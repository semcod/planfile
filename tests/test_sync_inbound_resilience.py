"""Unit tests for inbound sync resilience against pre-existing IDs and active execution leases."""

from __future__ import annotations

from pathlib import Path

import pytest

from planfile.core.store import PlanfileStore, Ticket
from planfile.sync.operations import sync_from_external


class _StubBackend:
    def __init__(self, tickets: list[dict]):
        self._tickets = tickets
        self.repo_name = "org/demo"

    def list_tickets(self, **_kwargs):
        return list(self._tickets)


def test_inbound_sync_updates_preexisting_generated_id_in_current_sprint(tmp_path: Path) -> None:
    store = PlanfileStore(tmp_path)
    store.create_ticket(
        Ticket(
            id="GITHUB-1022",
            name="Old title",
            sprint="current",
            status="open",
            description="existing",
        )
    )

    backend = _StubBackend(
        [
            {
                "id": "1022",
                "title": "Updated title from GitHub",
                "status": "open",
                "description": "updated body",
                "assignee": None,
                "labels": [],
                "url": "https://github.com/org/demo/issues/1022",
                "metadata": {},
            }
        ]
    )

    sync_from_external(backend, store, integration_name="github", dry_run=False)
    updated = store.get_ticket("GITHUB-1022")
    assert updated is not None
    assert updated.name == "Updated title from GitHub"
    assert updated.sprint == "current"


def test_inbound_sync_defers_active_lease_reconciliation_until_other_tickets_sync(tmp_path: Path) -> None:
    store = PlanfileStore(tmp_path)
    store.create_ticket(
        Ticket(
            id="GITHUB-100",
            name="Active leased ticket",
            sprint="current",
            status="in_progress",
            description="in flight",
            sync={"github": {"id": "100"}},
            execution={
                "state": "running",
                "assigned_to": "agent:codex",
                "lease_expires_at": "2099-01-01T00:00:00Z",
            },
        )
    )
    backend = _StubBackend(
        [
            {
                "id": "100",
                "title": "Active leased ticket",
                "status": "closed",
                "description": "closed remotely",
                "assignee": None,
                "labels": [],
                "url": "https://github.com/org/demo/issues/100",
                "metadata": {"state_reason": "completed"},
            },
            {
                "id": "101",
                "title": "Follow-up ticket",
                "status": "open",
                "description": "should still import",
                "assignee": None,
                "labels": [],
                "url": "https://github.com/org/demo/issues/101",
                "metadata": {},
            },
        ]
    )

    with pytest.raises(ValueError, match="inbound_terminal_transition_requires_execution_reconciliation"):
        sync_from_external(backend, store, integration_name="github", dry_run=False)

    # Ticket 100 kept its live execution lease untouched
    t100 = store.get_ticket("GITHUB-100")
    assert t100 is not None
    assert t100.status == "in_progress"
    assert t100.execution.assigned_to == "agent:codex"

    # Ticket 101 was STILL imported before the reconciliation error was raised
    t101 = store.get_ticket("GITHUB-101")
    assert t101 is not None
    assert t101.name == "Follow-up ticket"


def test_inbound_sync_aligns_duplicate_history_sprint_with_store_lookup_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = PlanfileStore(tmp_path)
    # Simulate a legacy ticket duplicated across two archived history sprints
    # where the newer sprint is first in store._ticket_lookup_sprints("PLF-176")
    # while _all_sprint_ids() lists history-2026-09-19 before history-2026-10-18.
    older = {
        "id": "history-2026-09-19",
        "tickets": {
            "PLF-176": {
                "id": "PLF-176",
                "name": "Older archived title",
                "status": "done",
                "sprint": "history-2026-09-19",
                "description": "old snapshot",
                "sync": {"github": {"id": "176"}},
                "updated_at": "2026-09-19T21:25:20+00:00",
            }
        },
    }
    newer = {
        "id": "history-2026-10-18",
        "tickets": {
            "PLF-176": {
                "id": "PLF-176",
                "name": "Newer archived title",
                "status": "done",
                "sprint": "history-2026-10-18",
                "description": "newer snapshot",
                "sync": {"github": {"id": "176"}},
                "updated_at": "2026-10-18T20:07:04+00:00",
            }
        },
    }
    store.save_sprint("history-2026-09-19", older)
    store.save_sprint("history-2026-10-18", newer)
    # Simulate indexed lookup returning the newer history sprint first.
    monkeypatch.setattr(
        store,
        "_ticket_lookup_sprints",
        lambda _tid: ["current", "history-2026-10-18", "history-2026-09-19"],
    )

    backend = _StubBackend(
        [
            {
                "id": "176",
                "title": "Synced archived title",
                "status": "closed",
                "description": "synced body",
                "assignee": None,
                "labels": ["done"],
                "url": "https://github.com/org/demo/issues/176",
                "metadata": {"state_reason": "completed"},
            }
        ]
    )

    sync_from_external(backend, store, integration_name="github", dry_run=False)
    refreshed = store.load_sprint("history-2026-10-18")
    assert refreshed["tickets"]["PLF-176"]["name"] == "Synced archived title"


def test_inbound_sync_preserves_local_dedupe_labels(tmp_path: Path) -> None:
    store = PlanfileStore(tmp_path)
    dedupe_label = "dedupe:scheduled-route-health-and-canonical-qualification-v1"
    store.create_ticket(
        Ticket(
            id="VA-076",
            name="Route health tracker",
            sprint="current",
            status="open",
            description="tracks route transitions",
            labels=["old-label", dedupe_label],
            sync={"github": {"id": "820"}},
        )
    )
    backend = _StubBackend(
        [
            {
                "id": "820",
                "title": "Route health tracker",
                "status": "open",
                "description": "tracks route transitions",
                "assignee": None,
                "labels": ["planfile", "routing-health"],
                "url": "https://github.com/org/demo/issues/820",
                "metadata": {},
            }
        ]
    )

    sync_from_external(backend, store, integration_name="github", dry_run=False)
    updated = store.get_ticket("VA-076")
    assert updated is not None
    assert updated.labels == ["planfile", "routing-health", dedupe_label]

