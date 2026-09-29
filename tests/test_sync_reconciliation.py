from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from planfile.sync.github import GitHubBackend
from planfile.sync.operations import check_sync_consistency
from planfile.sync.outbound import sync_to_external
from planfile.sync.state import SyncState


class FakeRepo:
    full_name = "test-owner/test-repo"

    def __init__(self, issues=None):
        self.issues = list(issues or [])
        self.created = []

    def get_labels(self):
        return []

    def create_label(self, **kwargs):
        return None

    def get_issues(self, **kwargs):
        return self.issues

    def create_issue(self, **kwargs):
        number = len(self.issues) + len(self.created) + 100
        new_issue = SimpleNamespace(
            number=number,
            html_url=f"https://github.com/{self.full_name}/issues/{number}",
            state="open",
            body=kwargs.get("body", ""),
            title=kwargs.get("title", ""),
            labels=[SimpleNamespace(name=lbl) for lbl in kwargs.get("labels", [])],
        )
        self.created.append(new_issue)
        self.issues.append(new_issue)
        return new_issue

    def get_issue(self, number):
        for issue in self.issues:
            if getattr(issue, "number", None) == int(number):
                return issue
        raise RuntimeError(f"Issue {number} not found (404)")


def _make_backend(repo, tmp_path=None):
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {
        "repo": repo.full_name,
        "token": "test-token",
        "cache_dir": str(tmp_path) if tmp_path else None,
        "cache_enabled": False,
    }
    backend.repo = repo
    backend._label_names = set()
    backend._mutation_interval = 0.0
    backend._last_mutation_at = 0.0
    return backend


def test_find_issue_prioritizes_open_over_closed_duplicates(tmp_path):
    marker = "<!-- planfile:deduplication-key=test-owner/test-repo:PLF-101 -->"
    closed_dup = SimpleNamespace(
        number=50,
        html_url="https://github.com/test-owner/test-repo/issues/50",
        state="closed",
        body=f"{marker}\nold closed duplicate",
    )
    open_dup = SimpleNamespace(
        number=75,
        html_url="https://github.com/test-owner/test-repo/issues/75",
        state="open",
        body=f"{marker}\ncurrent open issue",
    )
    repo = FakeRepo([closed_dup, open_dup])
    backend = _make_backend(repo, tmp_path)

    found = backend._find_issue_by_markers([marker])
    assert found is not None
    assert found.number == 75
    assert found.state == "open"


def test_find_issue_picks_canonical_lowest_open_duplicate(tmp_path):
    marker = "<!-- planfile:deduplication-key=test-owner/test-repo:PLF-102 -->"
    open_1 = SimpleNamespace(
        number=10,
        html_url="https://github.com/test-owner/test-repo/issues/10",
        state="open",
        body=f"{marker}\nfirst open issue",
    )
    open_2 = SimpleNamespace(
        number=20,
        html_url="https://github.com/test-owner/test-repo/issues/20",
        state="open",
        body=f"{marker}\nsecond open duplicate",
    )
    repo = FakeRepo([open_2, open_1])  # deliberately out of order
    backend = _make_backend(repo, tmp_path)

    found = backend._find_issue_by_markers([marker])
    assert found is not None
    assert found.number == 10
    assert getattr(found, "duplicate_numbers", []) == [20]


def test_find_issue_picks_highest_closed_when_no_open_exist(tmp_path):
    marker = "<!-- planfile:deduplication-key=test-owner/test-repo:PLF-103 -->"
    closed_1 = SimpleNamespace(
        number=30,
        html_url="https://github.com/test-owner/test-repo/issues/30",
        state="closed",
        body=f"{marker}\nolder closed",
    )
    closed_2 = SimpleNamespace(
        number=45,
        html_url="https://github.com/test-owner/test-repo/issues/45",
        state="closed",
        body=f"{marker}\nnewer closed",
    )
    repo = FakeRepo([closed_1, closed_2])
    backend = _make_backend(repo, tmp_path)

    found = backend._find_issue_by_markers([marker])
    assert found is not None
    assert found.number == 45
    assert getattr(found, "duplicate_numbers", []) == [30]


def test_create_ticket_serializes_and_prevents_duplicate_creation(tmp_path):
    repo = FakeRepo([])
    backend = _make_backend(repo, tmp_path)

    # First creation should create an issue
    ref1 = backend._create_ticket(
        "Issue 1",
        "Body 1",
        metadata={"deduplication_key": "test-owner/test-repo:PLF-200"},
    )
    assert len(repo.created) == 1
    assert ref1.id == str(repo.created[0].number)

    # Second creation with same deduplication key must reuse existing issue without calling create_issue
    ref2 = backend._create_ticket(
        "Issue 1 retry",
        "Body 1 retry",
        metadata={"deduplication_key": "test-owner/test-repo:PLF-200"},
    )
    assert len(repo.created) == 1
    assert ref2.id == ref1.id


class FakeStore:
    def __init__(self, base_dir, tickets=None):
        self.base_dir = Path(base_dir)
        self.tickets = dict(tickets or {})
        self.saved_sprints = {}

    def _all_sprint_ids(self):
        return ["current", "backlog"]

    def load_sprint(self, sprint_id):
        if sprint_id == "current":
            return {"id": "current", "tickets": self.tickets}
        return {"id": sprint_id, "tickets": {}}

    def save_sprint(self, sprint_id, data):
        self.saved_sprints[sprint_id] = data
        if sprint_id == "current":
            self.tickets = dict(data.get("tickets", {}))

    def load_backlog(self):
        return {"id": "backlog", "tickets": {}}

    def save_backlog(self, data):
        self.saved_sprints["backlog"] = data


def test_atomic_persistence_per_ticket(tmp_path):
    repo = FakeRepo([])
    backend = _make_backend(repo, tmp_path)

    ticket_1 = {
        "id": "PLF-1",
        "name": "Ticket One",
        "description": "First ticket",
        "status": "open",
    }
    ticket_2 = {
        "id": "PLF-2",
        "name": "Ticket Two",
        "description": "Second ticket",
        "status": "open",
    }
    store = FakeStore(tmp_path, {"PLF-1": ticket_1, "PLF-2": ticket_2})

    # Mock backend to fail on second ticket to prove first ticket is already atomically saved
    real_create_issue = repo.create_issue
    call_count = [0]

    def failing_create(**kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Network simulated crash on ticket 2")
        return real_create_issue(**kwargs)

    repo.create_issue = failing_create

    with pytest.raises(Exception):
        sync_to_external(
            backend,
            [("PLF-1", ticket_1), ("PLF-2", ticket_2)],
            dry_run=False,
            store=store,
            integration_name="github",
        )

    # Verify that PLF-1 was saved to sync state despite the failure on PLF-2
    sync_state = SyncState(tmp_path, "github", repository=repo.full_name)
    assert sync_state.get_remote_id("PLF-1") is not None
    # Verify that PLF-1 was saved in store
    assert "PLF-1" in store.tickets
    assert store.tickets["PLF-1"].get("sync", {}).get("github", {}).get("id") is not None
    # Verify PLF-2 was not saved
    assert sync_state.get_remote_id("PLF-2") is None


def test_check_sync_consistency_detects_mismatches_and_closed_remote(tmp_path):
    repo = FakeRepo([
        SimpleNamespace(
            number=101,
            html_url="https://github.com/test-owner/test-repo/issues/101",
            state="closed",
            body="closed body",
            title="Closed on GitHub",
        ),
        SimpleNamespace(
            number=102,
            html_url="https://github.com/test-owner/test-repo/issues/102",
            state="open",
            body="open body",
            title="Open on GitHub",
        ),
    ])
    backend = _make_backend(repo, tmp_path)

    store = FakeStore(tmp_path, {
        "PLF-1": {
            "id": "PLF-1",
            "name": "Ticket 1",
            "status": "open",
            "sync": {"github": {"id": "101", "url": "https://github.com/test-owner/test-repo/issues/101"}},
        },
        "PLF-2": {
            "id": "PLF-2",
            "name": "Ticket 2",
            "status": "open",
            "sync": {"github": {"id": "999"}},  # State has different id or missing remote
        },
        "PLF-3": {
            "id": "PLF-3",
            "name": "Ticket 3",
            "status": "open",
            # Missing sync in ticket, but present in state.yaml below
        }
    })

    sync_state = SyncState(tmp_path, "github", repository=repo.full_name)
    sync_state.save_sync({
        "PLF-1": "101",
        "PLF-2": "102",  # Mismatch: ticket has 999, state has 102
        "PLF-3": "103",  # Missing in ticket
        "PLF-ORPHAN": "200",  # Not in store
    })

    discrepancies = check_sync_consistency(
        store,
        integration_name="github",
        backend=backend,
    )

    kinds = {d["kind"] for d in discrepancies}
    assert "state_mismatch" in kinds
    assert "missing_ticket_mapping" in kinds
    assert "remote_closed" in kinds
    assert "orphaned_state_mapping" in kinds
    assert "remote_missing" in kinds
