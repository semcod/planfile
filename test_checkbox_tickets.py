"""Test checkbox-style ticket parsing in markdown backend."""
import tempfile
from pathlib import Path

from planfile.sync.markdown_backend import MarkdownFileBackend


def test_checkbox_ticket_parsing():
    """Test parsing of checkbox-style tickets from TODO.md."""
    
    # Create sample TODO.md content with checkbox-style tickets
    todo_content = """# TODO

## Completed Tasks
- [x] pyqual/cli.py:233 - Magic number: 50 - use named constant
- [x] pyqual/cli.py:456 - module execution block

## Pending Tasks
- [ ] pyqual/config.py:3 - Unused import: 'annotations'
- [ ] pyqual/config.py:40 - Magic number: 300 - use named constant
- [ ] pyqual/gates.py:436 - String concatenation can be converted to f-string
- [ ] pyqual/llm.py:61 - Magic number: 2000 - use named constant

---

## Structured Ticket (legacy format)
## 🟠 Legacy Ticket Title

**ID:** `legacy-ticket-20250329-123045`
**Priority:** high

Some description here...

---
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create TODO.md file
        todo_path = Path(tmpdir) / "TODO.md"
        todo_path.write_text(todo_content, encoding='utf-8')
        
        # Create empty CHANGELOG.md
        changelog_path = Path(tmpdir) / "CHANGELOG.md"
        changelog_path.write_text("# Changelog\n\n", encoding='utf-8')
        
        # Initialize backend
        backend = MarkdownFileBackend(
            changelog_file=str(changelog_path),
            todo_file=str(todo_path)
        )
        
        # Test list_tickets
        print("Testing _list_tickets():")
        tickets = backend._list_tickets()
        print(f"  Found {len(tickets)} tickets\n")
        
        # Check checkbox tickets vs structured
        # Checkbox tickets have pattern: file-line-8charhash (like TODO-4-97c8cb3c)
        # Structured tickets have longer IDs with text (like legacy-ticket-20250329-123045)
        checkbox_tickets = [t for t in tickets if re.match(r'^\w+-\d+-[a-f0-9]{8}$', t.id)]
        structured_tickets = [t for t in tickets if not re.match(r'^\w+-\d+-[a-f0-9]{8}$', t.id)]
        
        print(f"  Checkbox-style tickets: {len(checkbox_tickets)}")
        print(f"  Structured tickets: {len(structured_tickets)}\n")
        
        # Show checkbox tickets with status
        print("Checkbox ticket details:")
        for t in checkbox_tickets[:5]:  # Show first 5
            status_icon = "✓" if t.status == "completed" else " "
            print(f"  [{status_icon}] {t.id} - {t.status}")
        
        # Test status detection
        completed = [t for t in checkbox_tickets if t.status == "completed"]
        open_tickets = [t for t in checkbox_tickets if t.status == "open"]
        
        print(f"\nStatus summary:")
        print(f"  Completed: {len(completed)} (expected 2)")
        print(f"  Open: {len(open_tickets)} (expected 4)")
        
        # Test search
        print("\nTesting _search_tickets('magic'):")
        magic_tickets = backend._search_tickets("magic")
        for t in magic_tickets[:3]:
            print(f"  - {t.id} ({t.status})")
        
        # Test toggle status
        if checkbox_tickets:
            test_ticket = checkbox_tickets[0]
            print(f"\nTesting _toggle_checkbox_status for {test_ticket.id}:")
            print(f"  Current status: {test_ticket.status}")
            
            # Toggle to opposite status
            new_status = test_ticket.status != "completed"
            result = backend._toggle_checkbox_status(test_ticket.id, new_status)
            print(f"  Toggle result: {result}")
            
            # Verify change
            updated = backend._get_ticket(test_ticket.id)
            print(f"  New status: {updated.status}")
        
        # All assertions - focus on checkbox functionality
        assert len(checkbox_tickets) == 6, f"Expected 6 checkbox tickets, got {len(checkbox_tickets)}"
        assert len(completed) == 2, f"Expected 2 completed tickets, got {len(completed)}"
        assert len(open_tickets) == 4, f"Expected 4 open tickets, got {len(open_tickets)}"
        # Note: structured ticket support was already in planfile, we added checkbox support
        
        print("\n✅ All tests passed!")


if __name__ == "__main__":
    import re
    test_checkbox_ticket_parsing()
