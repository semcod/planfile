from __future__ import annotations

from types import SimpleNamespace
import pytest

from planfile.sync.operations import _process_external_ticket, sync_from_external
from planfile.sync.state import SyncState


class AmbiguousSyncState:
    def __init__(self):
        self._map = {
            "PLF-1": "100",
            "PLF-2": "100",  # ambiguous mapping for remote 100
            "PLF-3": "200",  # clean mapping for remote 200
        }

    def get_last_sync(self):
        return {"ticket_map": dict(self._map)}

    def get_remote_id(self, local_id: str) -> str | None:
        val = self._map.get(local_id)
        return str(val) if val is not None else None

    def get_local_id(self, remote_id: str) -> str | None:
        matches = [k for k, v in self._map.items() if str(v) == str(remote_id)]
        if len(matches) > 1:
            raise ValueError(f"ambiguous sync mapping for remote ticket {remote_id}")
        return matches[0] if matches else None

    def save_sync(self, updates):
        self._map.update(updates)


class FakeBackend:
    def __init__(self, issues):
        self._issues = issues

    def list_tickets(self, **kwargs):
        return self._issues


class FakeStore:
    def __init__(self, sections):
        self.base_dir = "/tmp/planfile-test-fake"
        self._sections = sections

    def is_initialized(self):
        return True

    def _all_sprint_ids(self):
        return list(self._sections.keys())

    def load_sprint(self, sprint_id):
        return self._sections.get(sprint_id, {"tickets": {}})

    def load_backlog(self):
        return self._sections.get("backlog", {"tickets": {}})

    def save_sprint(self, sprint_id, data):
        self._sections[sprint_id] = data

    def save_backlog(self, data):
        self._sections["backlog"] = data


def test_selective_sync_by_local_id_skips_unrelated_ambiguous_ticket():
    sections = {
        "current": {
            "tickets": {
                "PLF-1": {"id": "PLF-1", "name": "Ambiguous 1", "sync": {"github": {"id": 100}}},
                "PLF-2": {"id": "PLF-2", "name": "Ambiguous 2", "sync": {"github": {"id": 100}}},
                "PLF-3": {"id": "PLF-3", "name": "Target ticket", "sync": {"github": {"id": 200}}},
            }
        },
        "backlog": {"tickets": {}},
    }
    state = AmbiguousSyncState()

    ext_ambiguous = SimpleNamespace(
        id="100",
        name="Remote 100",
        description="",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/owner/repo/issues/100",
        key="owner/repo#100",
        metadata={},
    )
    ext_target = SimpleNamespace(
        id="200",
        name="Remote 200 Updated",
        description="updated body",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/owner/repo/issues/200",
        key="owner/repo#200",
        metadata={},
    )

    # 1. Directly with _process_external_ticket and ticket_ids={"PLF-3"}
    # The ambiguous remote ticket 100 must be skipped without triggering ValueError
    imported, updated = _process_external_ticket(
        ext_ambiguous,
        sections["current"],
        sections["backlog"],
        state,
        "github",
        False,
        0,
        0,
        sections=sections,
        ticket_ids={"PLF-3"},
    )
    assert (imported, updated) == (0, 0)

    # The target ticket 200 must be processed and updated
    imported, updated = _process_external_ticket(
        ext_target,
        sections["current"],
        sections["backlog"],
        state,
        "github",
        False,
        0,
        0,
        sections=sections,
        ticket_ids={"PLF-3"},
    )
    assert (imported, updated) == (0, 1)
    assert sections["current"]["tickets"]["PLF-3"]["name"] == "Remote 200 Updated"


def test_selective_sync_by_remote_id_skips_unrelated_ambiguous_ticket():
    sections = {
        "current": {
            "tickets": {
                "PLF-3": {"id": "PLF-3", "name": "Target ticket", "sync": {"github": {"id": 200}}},
            }
        },
        "backlog": {"tickets": {}},
    }
    state = AmbiguousSyncState()

    ext_ambiguous = SimpleNamespace(
        id="100",
        name="Remote 100",
        description="",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/owner/repo/issues/100",
        key="owner/repo#100",
        metadata={},
    )
    ext_target = SimpleNamespace(
        id="200",
        name="Remote 200 Updated via remote id",
        description="",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/owner/repo/issues/200",
        key="owner/repo#200",
        metadata={},
    )

    # Filtering by remote issue number "200" or "#200"
    imported, updated = _process_external_ticket(
        ext_ambiguous,
        sections["current"],
        sections["backlog"],
        state,
        "github",
        False,
        0,
        0,
        sections=sections,
        ticket_ids={"#200"},
    )
    assert (imported, updated) == (0, 0)

    imported, updated = _process_external_ticket(
        ext_target,
        sections["current"],
        sections["backlog"],
        state,
        "github",
        False,
        0,
        0,
        sections=sections,
        ticket_ids={"#200"},
    )
    assert (imported, updated) == (0, 1)
    assert sections["current"]["tickets"]["PLF-3"]["name"] == "Remote 200 Updated via remote id"


def test_selective_sync_fails_closed_when_ambiguous_ticket_is_explicitly_requested():
    sections = {
        "current": {
            "tickets": {
                "PLF-1": {"id": "PLF-1", "name": "Ambiguous 1", "sync": {"github": {"id": 100}}},
                "PLF-2": {"id": "PLF-2", "name": "Ambiguous 2", "sync": {"github": {"id": 100}}},
            }
        },
        "backlog": {"tickets": {}},
    }
    state = AmbiguousSyncState()

    ext_ambiguous = SimpleNamespace(
        id="100",
        name="Remote 100",
        description="",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/owner/repo/issues/100",
        key="owner/repo#100",
        metadata={},
    )

    # Explicitly requesting ambiguous local ticket PLF-1 must fail closed
    with pytest.raises(ValueError, match="ambiguous sync mapping for remote ticket 100"):
        _process_external_ticket(
            ext_ambiguous,
            sections["current"],
            sections["backlog"],
            state,
            "github",
            False,
            0,
            0,
            sections=sections,
            ticket_ids={"PLF-1"},
        )

    # Explicitly requesting ambiguous remote ticket 100 must fail closed
    with pytest.raises(ValueError, match="ambiguous sync mapping for remote ticket 100"):
        _process_external_ticket(
            ext_ambiguous,
            sections["current"],
            sections["backlog"],
            state,
            "github",
            False,
            0,
            0,
            sections=sections,
            ticket_ids={"100"},
        )


def test_sync_from_external_end_to_end_selective_filter(tmp_path, monkeypatch):
    from planfile.core.store import PlanfileStore
    store = PlanfileStore(str(tmp_path))
    store.init()
    ticket_data = {
        "id": "PLF-3",
        "name": "Local PLF-3",
        "status": "open",
        "sync": {"github": {"id": 200}},
    }
    store.save_sprint("current", {"tickets": {"PLF-3": ticket_data}})

    # Populate sync state with an ambiguous mapping for 100
    state = SyncState(tmp_path, "github", repository="test-owner/test-repo")
    state.save_sync({"PLF-1": "100", "PLF-2": "100", "PLF-3": "200"})

    ext_ambiguous = SimpleNamespace(
        id="100",
        name="Remote 100",
        description="",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/test-owner/test-repo/issues/100",
        key="test-owner/test-repo#100",
        metadata={},
    )
    ext_target = SimpleNamespace(
        id="200",
        name="Remote 200 From GitHub",
        description="updated",
        status="open",
        assignee=None,
        labels=[],
        url="https://github.com/test-owner/test-repo/issues/200",
        key="test-owner/test-repo#200",
        metadata={},
    )
    backend = FakeBackend([ext_ambiguous, ext_target])

    # End-to-end sync_from_external with selective ticket filter PLF-3
    sync_from_external(
        backend,
        store,
        dry_run=False,
        integration_name="github",
        ticket_ids=["PLF-3"],
    )

    # PLF-3 should be updated, and no crash occurred on ambiguous ticket 100
    updated_sprint = store.load_sprint("current")
    assert updated_sprint["tickets"]["PLF-3"]["name"] == "Remote 200 From GitHub"

