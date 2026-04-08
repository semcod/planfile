from tempfile import TemporaryDirectory
from pathlib import Path
type Ticket = object  # Assuming Ticket is a custom type or class

# Neighboring function:
def create_temp_files(mixed_content):
    with TemporaryDirectory() as tmpdir:
        todo_path = Path(tmpdir) / "TODO.md"
        todo_path.write_text(mixed_content, encoding='utf-8')

        changelog_path = Path(tmpdir) / "CHANGELOG.md"
        changelog_path.write_text("# Changelog\n\n", encoding='utf-8')

        return str(todo_path), str(changelog_path)

# Neighboring function:
def categorize_tickets(tickets):
    checkbox_tickets = [t for t in tickets if len(t.id.split('-')) >= 3 and len(t.id.split('-')[-1]) == 8]
    structured_tickets = [t for t in tickets if not (len(t.id.split('-')) >= 3 and len(t.id.split('-')[-1]) == 8)]

    completed = [t for t in tickets if t.status == "completed"]
    open_tickets = [t for t in tickets if t.status == "open"]

    return checkbox_tickets, structured_tickets, completed, open_tickets

# Extracted function to categorize tickets by status
def filter_by_status(tickets, status):
    return [t for t in tickets if t.status == status]

# Extracted function to categorize tickets by ID pattern
def filter_by_id_pattern(tickets, pattern):
    return [t for t in tickets if len(t.id.split('-')) >= 3 and len(t.id.split('-')[-1]) == 8]

# Refactored parse_tickets function
def parse_tickets(backend):
    tickets = backend._list_tickets()
    print(f"Found {len(tickets)} tickets total\n")

    checkbox_tickets = filter_by_id_pattern(tickets, 'checkbox')
    structured_tickets = filter_by_id_pattern(tickets, 'structured')

    completed = filter_by_status(tickets, 'completed')
    open_tickets = filter_by_status(tickets, 'open')

    print(f"Checkbox-style tickets: {len(checkbox_tickets)}")
    print(f"Structured tickets: {len(structured_tickets)}")
    print(f"Completed: {len(completed)}")
    print(f"Open: {len(open_tickets)}")

    return checkbox_tickets, structured_tickets, completed, open_tickets