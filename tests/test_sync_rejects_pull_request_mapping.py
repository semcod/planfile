"""Regression tests for ticket-130 / semcod/planfile#126.

An outbound create must never report success and persist a ticket_map entry
for an id it cannot actually vouch for as the created issue.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml

from planfile.sync.github import GitHubBackend
from planfile.sync.outbound import sync_to_external
from planfile.sync.state import SyncState


class FakeIssue(SimpleNamespace):
    pass


class FakeRepoWithPullRequest:
    """A repo where issue number 19 is actually a merged pull request."""

    full_name = "semcod/monag"

    def get_issue(self, number):
        if number == 19:
            return FakeIssue(number=19, title="fix: unrelated PR", pull_request=object())
        raise AssertionError(f"unexpected get_issue({number})")

    def get_labels(self):
        return []


def test_get_ticket_rejects_a_pull_request_number():
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "semcod/monag"}
    backend.repo = FakeRepoWithPullRequest()

    with pytest.raises(ValueError, match="pull request"):
        backend.get_ticket("19")


class BackendCreatesButReadbackIsAPullRequest:
    """create_ticket reports id 19, but a readback shows 19 is a pull request.

    Models the reproduction in #126: a create call that returns/resolves to a
    number the code did not actually mint as a fresh issue.
    """

    def __init__(self):
        self.created = []

    def create_ticket(self, ticket):
        self.created.append(ticket)
        return {"id": "19", "url": "https://github.com/semcod/monag/issues/19"}

    def get_ticket(self, ticket_id):
        raise ValueError(f"semcod/monag#{ticket_id} is a pull request, not an issue")

    def update_ticket(self, external_id, **fields):
        raise AssertionError("not expected: this ticket has no known external id yet")

    def list_tickets(self):
        return []


def _source(tmp_path):
    path = tmp_path / "tickets.planfile.yaml"
    data = {
        "project": {"name": "semcod/monag"},
        "integrations": {"github": {"repo": "semcod/monag"}},
        "backlog": {"tickets": {"PLF-003": {"title": "Fleet refactoring metrics", "integration": "github"}}},
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    store = SimpleNamespace(base_dir=tmp_path / ".planfile")
    return path, data, store


def test_create_whose_readback_is_a_pull_request_is_reported_failed_not_created(tmp_path):
    path, data, store = _source(tmp_path)
    backend = BackendCreatesButReadbackIsAPullRequest()

    with pytest.raises(Exception):
        sync_to_external(
            backend, list(data["backlog"]["tickets"].items()), False, store, "github", path, data
        )

    saved = yaml.safe_load(path.read_text())
    assert "sync" not in saved["backlog"]["tickets"]["PLF-003"]

    state = SyncState(store.base_dir, "github")
    assert state.get_remote_id("PLF-003") is None
