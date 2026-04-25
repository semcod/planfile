"""Tests for ticket file filtering functionality."""

import pytest
from datetime import datetime
from planfile.core.models import Ticket, TicketSource


def test_ticket_model_with_files():
    """Test Ticket model with files field."""
    ticket = Ticket(
        id="PLF-001",
        title="Test ticket",
        name="test-ticket",
        files=["src/main.py", "lib/utils.py"]
    )
    
    assert ticket.files == ["src/main.py", "lib/utils.py"]
    assert len(ticket.files) == 2


def test_ticket_model_with_file():
    """Test Ticket model with single file field."""
    ticket = Ticket(
        id="PLF-002",
        title="Test ticket",
        name="test-ticket",
        file="src/main.py"
    )
    
    assert ticket.file == "src/main.py"
    assert ticket.files == []


def test_ticket_model_default_files():
    """Test Ticket model with default empty files."""
    ticket = Ticket(
        id="PLF-003",
        title="Test ticket",
        name="test-ticket"
    )
    
    assert ticket.files == []
    assert ticket.file is None


def test_store_filter_by_files():
    """Test store filtering by files field."""
    from planfile.core.store_tickets import TicketStoreMixin
    
    tickets = [
        Ticket(id="PLF-001", title="Ticket 1", name="ticket-1", files=["src/main.py"]),
        Ticket(id="PLF-002", title="Ticket 2", name="ticket-2", files=["lib/utils.py"]),
        Ticket(id="PLF-003", title="Ticket 3", name="ticket-3", files=["src/main.py", "lib/test.py"]),
        Ticket(id="PLF-004", title="Ticket 4", name="ticket-4", files=[]),
    ]
    
    store = TicketStoreMixin()
    
    # Filter by src/* pattern
    filtered = store._apply_filters(tickets, files=["src/*"])
    assert len(filtered) == 2
    assert any(t.id == "PLF-001" for t in filtered)
    assert any(t.id == "PLF-003" for t in filtered)
    
    # Filter by lib/* pattern
    filtered = store._apply_filters(tickets, files=["lib/*"])
    assert len(filtered) == 2
    assert any(t.id == "PLF-002" for t in filtered)
    assert any(t.id == "PLF-003" for t in filtered)


def test_store_filter_by_file():
    """Test store filtering by single file field."""
    from planfile.core.store_tickets import TicketStoreMixin
    
    tickets = [
        Ticket(id="PLF-001", title="Ticket 1", name="ticket-1", file="src/main.py"),
        Ticket(id="PLF-002", title="Ticket 2", name="ticket-2", file="lib/utils.py"),
        Ticket(id="PLF-003", title="Ticket 3", name="ticket-3", file=None),
    ]
    
    store = TicketStoreMixin()
    
    # Filter by src/* pattern
    filtered = store._apply_filters(tickets, files=["src/*"])
    assert len(filtered) == 1
    assert filtered[0].id == "PLF-001"
    
    # Filter by lib/* pattern
    filtered = store._apply_filters(tickets, files=["lib/*"])
    assert len(filtered) == 1
    assert filtered[0].id == "PLF-002"


def test_store_filter_by_files_and_file():
    """Test store filtering with both files and file fields."""
    from planfile.core.store_tickets import TicketStoreMixin
    
    tickets = [
        Ticket(id="PLF-001", title="Ticket 1", name="ticket-1", files=["src/main.py"], file=None),
        Ticket(id="PLF-002", title="Ticket 2", name="ticket-2", files=[], file="lib/utils.py"),
        Ticket(id="PLF-003", title="Ticket 3", name="ticket-3", files=["src/test.py"], file="src/main.py"),
    ]
    
    store = TicketStoreMixin()
    
    # Filter by src/* pattern - should match PLF-001 (files) and PLF-003 (file)
    filtered = store._apply_filters(tickets, files=["src/*"])
    assert len(filtered) == 2
    assert any(t.id == "PLF-001" for t in filtered)
    assert any(t.id == "PLF-003" for t in filtered)
    
    # Filter by lib/* pattern - should match only PLF-002
    filtered = store._apply_filters(tickets, files=["lib/*"])
    assert len(filtered) == 1
    assert filtered[0].id == "PLF-002"


def test_store_filter_by_files_glob_pattern():
    """Test store filtering with glob patterns."""
    from planfile.core.store_tickets import TicketStoreMixin
    
    tickets = [
        Ticket(id="PLF-001", title="Ticket 1", name="ticket-1", files=["_archive/test.py"]),
        Ticket(id="PLF-002", title="Ticket 2", name="ticket-2", files=["src/main.py"]),
        Ticket(id="PLF-003", title="Ticket 3", name="ticket-3", files=["lib/utils.py"]),
    ]
    
    store = TicketStoreMixin()
    
    # Filter by _archive* pattern
    filtered = store._apply_filters(tickets, files=["_archive*"])
    assert len(filtered) == 1
    assert filtered[0].id == "PLF-001"
    
    # Filter by *.py pattern
    filtered = store._apply_filters(tickets, files=["*.py"])
    assert len(filtered) == 3


def test_store_filter_no_files():
    """Test store filtering with no files field."""
    from planfile.core.store_tickets import TicketStoreMixin
    
    tickets = [
        Ticket(id="PLF-001", title="Ticket 1", name="ticket-1", files=[]),
        Ticket(id="PLF-002", title="Ticket 2", name="ticket-2", files=[]),
    ]
    
    store = TicketStoreMixin()
    
    # Filter should return empty
    filtered = store._apply_filters(tickets, files=["src/*"])
    assert len(filtered) == 0


def test_store_filter_multiple_patterns():
    """Test store filtering with multiple file patterns."""
    from planfile.core.store_tickets import TicketStoreMixin
    
    tickets = [
        Ticket(id="PLF-001", title="Ticket 1", name="ticket-1", files=["src/main.py"]),
        Ticket(id="PLF-002", title="Ticket 2", name="ticket-2", files=["lib/utils.py"]),
        Ticket(id="PLF-003", title="Ticket 3", name="ticket-3", files=["test/test.py"]),
    ]
    
    store = TicketStoreMixin()
    
    # Filter by multiple patterns
    filtered = store._apply_filters(tickets, files=["src/*", "lib/*"])
    assert len(filtered) == 2
    assert any(t.id == "PLF-001" for t in filtered)
    assert any(t.id == "PLF-002" for t in filtered)


def test_store_matches_files():
    """Test _matches_files method."""
    from planfile.core.store_tickets import TicketStoreMixin
    
    store = TicketStoreMixin()
    
    ticket_with_files = Ticket(
        id="PLF-001",
        title="Ticket 1",
        name="ticket-1",
        files=["src/main.py", "lib/utils.py"]
    )
    
    assert store._matches_files(ticket_with_files, ["src/*"]) == True
    assert store._matches_files(ticket_with_files, ["lib/*"]) == True
    assert store._matches_files(ticket_with_files, ["test/*"]) == False
    
    ticket_with_file = Ticket(
        id="PLF-002",
        title="Ticket 2",
        name="ticket-2",
        file="src/main.py"
    )
    
    assert store._matches_files(ticket_with_file, ["src/*"]) == True
    assert store._matches_files(ticket_with_file, ["lib/*"]) == False


def test_ticket_create_with_files():
    """Test creating ticket with files."""
    from planfile import Planfile, TicketSource
    from unittest.mock import Mock
    
    # Mock the Planfile store
    mock_store = Mock()
    mock_store.project_dir = "/tmp/test"
    mock_store.create_ticket = Mock(return_value=Ticket(
        id="PLF-001",
        title="Test ticket",
        name="test-ticket",
        files=["src/main.py"]
    ))
    
    ticket_data = {
        "title": "Test ticket",
        "priority": "normal",
        "sprint": "current",
        "source": TicketSource(tool="human"),
        "labels": [],
        "description": "",
        "files": ["src/main.py"]
    }
    
    ticket = mock_store.create_ticket(**ticket_data)
    assert ticket.files == ["src/main.py"]
