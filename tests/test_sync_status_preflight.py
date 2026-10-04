"""Legacy ticket status aliases and invalid-state writes must agree."""
from unittest.mock import Mock

import pytest

from planfile.core.models.base import TicketStatus
from planfile.sync.github import GitHubBackend


@pytest.mark.parametrize("status", ["backlog", "todo", "doing", "active", "inprogress",
                                    " IN-PROGRESS ", TicketStatus.open])
def test_legacy_active_aliases_project_to_open(status):
    assert GitHubBackend.project_remote_status(status) == "open"


@pytest.mark.parametrize("status", ["close", "resolved", "completed", "cancelled",
                                    TicketStatus.done])
def test_legacy_terminal_aliases_project_to_closed(status):
    assert GitHubBackend.project_remote_status(status) == "closed"


def test_invalid_direct_update_rejects_before_any_provider_access():
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.repo = Mock()
    with pytest.raises(ValueError, match="sync_github_status_unsupported"):
        backend._update_ticket("42", body="new body", status="unknown-state",
                               labels=["managed"], assignee="someone")
    assert not backend.repo.mock_calls


def test_batch_preflight_rejects_late_invalid_status_without_label_effects():
    backend = GitHubBackend.__new__(GitHubBackend)
    backend._canonical_labels = Mock()
    tickets = [("PLF-1", {"status": "open"}), ("PLF-2", {"status": "unknown-state"})]
    with pytest.raises(ValueError, match="sync_github_status_unsupported"):
        backend.preflight(tickets)
    assert not backend._canonical_labels.mock_calls


def test_batch_preflight_accepts_backlog_and_validates_labels():
    backend = GitHubBackend.__new__(GitHubBackend)
    backend._canonical_labels = Mock()
    backend.preflight([("PLF-1", {"status": "backlog", "labels": ["managed"],
                                  "priority": "normal"})])
    backend._canonical_labels.assert_called_once_with(["managed"], "normal")
