"""Tests for ticket status normalization in core models and sync."""

from unittest.mock import MagicMock
from planfile.core.models.base import TicketStatus
from planfile.core.models.ticket import Ticket
from planfile.sync.github import GitHubBackend


def test_ticket_model_status_normalization_closed():
    """Verify closed/resolved/completed aliases normalize to TicketStatus.done."""
    t1 = Ticket(id="PLF-1", name="Task 1", status="closed")
    assert t1.status == TicketStatus.done

    t2 = Ticket(id="PLF-2", name="Task 2", status="CLOSED")
    assert t2.status == TicketStatus.done

    t3 = Ticket(id="PLF-3", name="Task 3", status="resolved")
    assert t3.status == TicketStatus.done

    t4 = Ticket(id="PLF-4", name="Task 4", status="completed")
    assert t4.status == TicketStatus.done


def test_ticket_model_status_normalization_in_progress():
    """Verify in-progress aliases normalize to TicketStatus.in_progress."""
    t1 = Ticket(id="PLF-5", name="Task 5", status="in-progress")
    assert t1.status == TicketStatus.in_progress

    t2 = Ticket(id="PLF-6", name="Task 6", status="inprogress")
    assert t2.status == TicketStatus.in_progress

    t3 = Ticket(id="PLF-7", name="Task 7", status="doing")
    assert t3.status == TicketStatus.in_progress


def test_ticket_model_status_normalization_open_and_canceled():
    """Verify todo, backlog, and cancelled aliases normalize properly."""
    t1 = Ticket(id="PLF-8", name="Task 8", status="todo")
    assert t1.status == TicketStatus.open

    t2 = Ticket(id="PLF-9", name="Task 9", status="backlog")
    assert t2.status == TicketStatus.open

    t3 = Ticket(id="PLF-10", name="Task 10", status="cancelled")
    assert t3.status == TicketStatus.canceled


def test_ticket_model_validate_dict_normalization():
    """Verify model_validate from dict (YAML / JSON deserialization) normalizes status."""
    data = {
        "id": "PLF-11",
        "name": "Task 11",
        "status": "closed",
        "priority": "high",
    }
    ticket = Ticket.model_validate(data)
    assert ticket.status == TicketStatus.done


def test_github_sync_issue_to_ticket_status_normalization():
    """Verify GitHubBackend._issue_to_ticket_status maps closed state to done."""
    # Create backend instance with mock github
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.repo = MagicMock()
    backend.repo.full_name = "test/repo"
    backend.config = {}

    # Mock issue with closed state
    mock_issue = MagicMock()
    mock_issue.number = 42
    mock_issue.title = "Sample closed issue"
    mock_issue.body = "Issue description"
    mock_issue.html_url = "https://github.com/test/repo/issues/42"
    mock_issue.state = "closed"
    mock_issue.state_reason = "completed"
    mock_issue.assignee = None
    mock_issue.labels = []
    mock_issue.updated_at = None

    state = backend._issue_to_ticket_status(mock_issue)
    assert state.status == "done"
    assert state.id == "42"
    assert state.name == "Sample closed issue"
