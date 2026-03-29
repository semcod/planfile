#!/usr/bin/env python3
"""Test parsing of TODO.md with mixed formats."""

import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from planfile.sync.markdown_backend import MarkdownFileBackend


def test_mixed_format_parsing():
    """Test that different TODO.md formats are parsed correctly."""
    
    # Mixed format content - various edge cases
    mixed_content = """# Planfile TODO List

## Mixed Format Section

### Subsection with checkboxes
- [ ] Plain checkbox item without file reference
- [x] Completed plain item
  - [ ] Nested checkbox (indented)
  - [x] Nested completed

### Checkboxes with file references  
- [ ] pyqual/cli.py:233 - Magic number: 50
- [x] pyqual/config.py:3 - Fixed unused import

### Structured Tickets (legacy format)
## 🟠 Refactor cli.py

**ID:** `refactor-cli-20250329-123045`
**Priority:** high
**Labels:** refactoring, cli

Need to break down the large functions.

---

## 🟡 Update documentation

**ID:** `update-docs-20250329-123046`  
**Priority:** medium

Update README with new examples.

---

### More checkboxes after structured
- [ ] Another pending task
- [x] Another completed task

### Edge cases
- [ ] Item with **bold** text
- [x] Item with `code` inline
- [ ] Item with [link](http://example.com)
- [ ] Very long item description that goes on and on and describes something in great detail

## Empty checkbox
- [ ]

## Not a checkbox (bullet only)
- Regular bullet item (should not be a ticket)
- Another bullet

## Completed Tasks (from original TODO.md)
- [x] Identify and remove unnecessary files
- [x] Organize summaries into docs/
- [x] Run examples to ensure correctness

## Pending Improvements
- [x] Consider implementing cache warming
- [ ] Add performance metrics
- [x] Implement async I/O
- [ ] Add connection pooling

# Notes on Examples Directory
The following warnings in the examples/ directory are intentional:
- Example functions are expected patterns
- These patterns make examples more readable
- Warnings about unused imports can be ignored

---

# TODO
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"
        todo_path.write_text(mixed_content, encoding='utf-8')
        
        changelog_path = Path(tmpdir) / "CHANGELOG.md"
        changelog_path.write_text("# Changelog\n\n", encoding='utf-8')
        
        backend = MarkdownFileBackend(
            changelog_file=str(changelog_path),
            todo_file=str(todo_path)
        )
        
        tickets = backend._list_tickets()
        
        print(f"Found {len(tickets)} tickets total\n")
        
        # Debug: show all ticket IDs
        print("--- All Ticket IDs ---")
        for t in tickets:
            print(f"  ID: '{t.id}' | status: {t.status}")
        print()
        
        # Categorize
        checkbox_tickets = [t for t in tickets if len(t.id.split('-')) >= 3 and len(t.id.split('-')[-1]) == 8]
        structured_tickets = [t for t in tickets if not (len(t.id.split('-')) >= 3 and len(t.id.split('-')[-1]) == 8)]
        
        completed = [t for t in tickets if t.status == "completed"]
        open_tickets = [t for t in tickets if t.status == "open"]
        
        print(f"Checkbox-style tickets: {len(checkbox_tickets)}")
        print(f"Structured tickets: {len(structured_tickets)}")
        print(f"Completed: {len(completed)}")
        print(f"Open: {len(open_tickets)}")
        
        print("\n--- All Tickets ---")
        for t in tickets:
            icon = "✓" if t.status == "completed" else "○"
            print(f"[{icon}] {t.id} ({t.status})")
        
        # Check specific expectations
        print("\n--- Checking Specific Items ---")
        
        # Should NOT be tickets (plain bullets)
        plain_bullets_as_tickets = [t for t in tickets if "bullet" in t.id.lower()]
        print(f"Plain bullets incorrectly parsed as tickets: {len(plain_bullets_as_tickets)}")
        
        # Should be tickets (checkboxes)
        magic_number_tickets = [t for t in tickets if "magic" in t.id.lower() or "pyqual" in t.id.lower()]
        print(f"Magic number / pyqual tickets found: {len(magic_number_tickets)}")
        
        # Test search
        print("\n--- Search Tests ---")
        for query in ["refactor", "documentation", "magic"]:
            results = backend._search_tickets(query)
            print(f"Search '{query}': {len(results)} results")
        
        # Assertions
        print("\n--- Assertions ---")
        
        # We expect at least these many checkboxes
        expected_checkbox_min = 15
        if len(checkbox_tickets) >= expected_checkbox_min:
            print(f"✓ Found {len(checkbox_tickets)} checkbox tickets (expected >= {expected_checkbox_min})")
        else:
            print(f"✗ Found {len(checkbox_tickets)} checkbox tickets (expected >= {expected_checkbox_min})")
            
        # Check that plain bullets are NOT parsed as tickets
        # (line "- Regular bullet item" should not create a ticket)
        if len(plain_bullets_as_tickets) == 0:
            print("✓ Plain bullet items correctly NOT parsed as tickets")
        else:
            print(f"✗ Plain bullet items incorrectly parsed as tickets: {plain_bullets_as_tickets}")
        
        # Check structured tickets exist
        if len(structured_tickets) >= 1:
            print(f"✓ Found {len(structured_tickets)} structured tickets")
        else:
            print(f"✗ No structured tickets found")
        
        # Check status detection
        expected_completed = 8  # Count from the test data
        if len(completed) >= expected_completed:
            print(f"✓ Found {len(completed)} completed tickets (expected >= {expected_completed})")
        else:
            print(f"✗ Found {len(completed)} completed tickets (expected >= {expected_completed})")
        
        return len(checkbox_tickets) >= expected_checkbox_min and len(plain_bullets_as_tickets) == 0


if __name__ == "__main__":
    success = test_mixed_format_parsing()
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")
    sys.exit(0 if success else 1)
