"""Markdown file backend for managing CHANGELOG.md and TODO.md files."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from planfile.sync.base import BasePMBackend, TicketRef, TicketStatus


class MarkdownFileBackend(BasePMBackend):
    """Backend for managing tickets in CHANGELOG.md and TODO.md files."""

    def __init__(
        self,
        changelog_file: str = "CHANGELOG.md",
        todo_file: str = "TODO.md",
        **kwargs
    ):
        """
        Initialize markdown backend.
        
        Args:
            changelog_file: Path to CHANGELOG.md file
            todo_file: Path to TODO.md file
        """
        config = {
            "changelog_file": changelog_file,
            "todo_file": todo_file,
            **kwargs
        }
        super().__init__(config)

        self.changelog_path = Path(self.config["changelog_file"])
        self.todo_path = Path(self.config["todo_file"])

        # Ensure files exist
        self._ensure_files_exist()

    def _validate_config(self) -> None:
        """Validate markdown backend configuration."""
        # No specific validation needed for file paths
        pass

    def _ensure_files_exist(self) -> None:
        """Ensure markdown files exist with basic structure."""
        # Ensure CHANGELOG.md exists
        if not self.changelog_path.exists():
            self.changelog_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.changelog_path, 'w', encoding='utf-8') as f:
                f.write("# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n")

        # Ensure TODO.md exists
        if not self.todo_path.exists():
            self.todo_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.todo_path, 'w', encoding='utf-8') as f:
                f.write("# TODO\n\nTasks and improvements to be done.\n\n")

    def _create_ticket(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TicketRef:
        """Create a new ticket in the appropriate markdown file."""
        # Determine target file based on labels or content
        target_file = self._determine_target_file(title, labels, body)

        # Check for duplicates by title before generating ID
        if self._ticket_exists_by_title(title, target_file):
            raise ValueError(f"Ticket already exists: {title}")

        # Format the ticket entry
        entry = self._format_ticket_entry(
            ticket_id="",  # Will be generated after formatting
            title=title,
            body=body,
            labels=labels,
            priority=priority,
            assignee=assignee,
            metadata=metadata
        )

        # Generate ticket ID and update entry
        ticket_id = self._generate_ticket_id(title, target_file)
        entry = entry.replace("**ID:** ``", f"**ID:** `{ticket_id}`")

        # Write to file
        self._write_ticket_to_file(entry, target_file)

        return self.build_ticket_ref(
            id=ticket_id,
            url=str(target_file),
            status="open"
        )

    def _determine_target_file(self, title: str, labels: list[str] | None, body: str) -> Path:
        """Determine which file to write the ticket to based on content."""
        # Check if it's a changelog entry (completed tasks, releases, etc.)
        changelog_keywords = ["release", "released", "completed", "fixed", "added", "removed", "changed"]
        todo_keywords = ["todo", "fix", "implement", "add", "update", "refactor"]

        title_lower = title.lower()
        body_lower = body.lower()

        # Check labels
        if labels:
            if any(label.lower() in ["changelog", "release", "completed"] for label in labels):
                return self.changelog_path
            if any(label.lower() in ["todo", "task", "bug"] for label in labels):
                return self.todo_path

        # Check title and body
        if any(keyword in title_lower or keyword in body_lower for keyword in changelog_keywords):
            return self.changelog_path
        if any(keyword in title_lower or keyword in body_lower for keyword in todo_keywords):
            return self.todo_path

        # Default to TODO.md
        return self.todo_path

    def _generate_ticket_id(self, title: str, target_file: Path) -> str:
        """Generate a unique ticket ID based on title and timestamp."""
        # Create a slug from title
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title).strip()
        slug = re.sub(r'[-\s]+', '-', slug)

        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{slug}-{timestamp}"

    def _ticket_exists(self, ticket_id: str, target_file: Path) -> bool:
        """Check if a ticket already exists in the file."""
        with open(target_file, encoding='utf-8') as f:
            content = f.read()
            return ticket_id in content

    def _ticket_exists_by_title(self, title: str, target_file: Path) -> bool:
        """Check if a ticket with the given title already exists in the file."""
        if not target_file.exists():
            return False

        with open(target_file, encoding='utf-8') as f:
            content = f.read()

        # Look for "## <title>" pattern (case insensitive)
        # Escape special regex characters in title
        escaped_title = re.escape(title)
        pattern = rf"##\s+(?:[🔴🟠🟡🟢⚪]\s+)?{re.escape(title)}\s*$"

        # Check each line
        for line in content.split('\n'):
            if re.match(pattern, line, re.IGNORECASE):
                return True

        return False

    def _format_ticket_entry(
        self,
        ticket_id: str,
        title: str,
        body: str,
        labels: list[str] | None,
        priority: str | None,
        assignee: str | None,
        metadata: dict[str, Any] | None
    ) -> str:
        """Format a ticket entry for markdown file."""
        lines = []

        # Header with priority indicator
        priority_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }.get(priority, "⚪")

        lines.append(f"## {priority_emoji} {title}")
        lines.append("")

        # Metadata
        lines.append(f"**ID:** `{ticket_id}`")
        if priority:
            lines.append(f"**Priority:** {priority}")
        if assignee:
            lines.append(f"**Assignee:** {assignee}")
        if labels:
            lines.append(f"**Labels:** {', '.join(labels)}")
        lines.append("")

        # Body
        if body:
            lines.append(body)
            lines.append("")

        # Separator
        lines.append("---")
        lines.append("")

        return "\n".join(lines)

    def _write_ticket_to_file(self, entry: str, target_file: Path) -> None:
        """Write a ticket entry to the markdown file."""
        with open(target_file, 'r+', encoding='utf-8') as f:
            content = f.read()

            # Find position to insert (after header, before first entry or at end)
            if target_file.name == "CHANGELOG.md":
                # For changelog, insert after header
                header_end = content.find("\n\n", content.find("# Changelog"))
                if header_end == -1:
                    header_end = content.find("\n", content.find("# Changelog"))
                insert_pos = header_end + 2 if header_end > 0 else len(content)
            else:
                # For TODO, insert after header
                header_end = content.find("\n\n", content.find("# TODO"))
                if header_end == -1:
                    header_end = content.find("\n", content.find("# TODO"))
                insert_pos = header_end + 2 if header_end > 0 else len(content)

            # Insert entry
            new_content = content[:insert_pos] + entry + content[insert_pos:]

            # Write back
            f.seek(0)
            f.write(new_content)
            f.truncate()

    def _update_ticket(
        self,
        ticket_id: str,
        title: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
    ) -> None:
        """Update an existing ticket in the markdown files."""
        # Find which file contains the ticket
        target_file = self._find_ticket_file(ticket_id)
        if not target_file:
            raise ValueError(f"Ticket not found: {ticket_id}")

        # Read file content
        with open(target_file, encoding='utf-8') as f:
            content = f.read()

        # Find and update the ticket section
        ticket_pattern = rf"(## .+?\n\n.*?ID: `{ticket_id}`.*?)(---\n)"
        match = re.search(ticket_pattern, content, re.DOTALL)

        if not match:
            raise ValueError(f"Ticket section not found: {ticket_id}")

        # Update the ticket content
        ticket_content = match.group(1)

        # Update title if provided
        if title:
            ticket_content = re.sub(r"## .+", f"## {title}", ticket_content)

        # Update other fields as needed
        # (This is a simplified version - you might want more sophisticated updates)

        # Replace in content
        new_content = content.replace(match.group(0), ticket_content + "---\n")

        # Write back
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

    def _find_ticket_file(self, ticket_id: str) -> Path | None:
        """Find which file contains the given ticket ID."""
        for file_path in [self.changelog_path, self.todo_path]:
            if file_path.exists():
                with open(file_path, encoding='utf-8') as f:
                    if ticket_id in f.read():
                        return file_path
        return None

    def _get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get ticket status from markdown files."""
        target_file = self._find_ticket_file(ticket_id)
        if not target_file:
            raise ValueError(f"Ticket not found: {ticket_id}")

        # Parse ticket status (simplified - assumes all are open)
        return self.build_ticket_status(
            id=ticket_id,
            status="open",
            updated_at=None
        )

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
    ) -> list[TicketStatus]:
        """List tickets from markdown files."""
        tickets = []

        for file_path in [self.changelog_path, self.todo_path]:
            if file_path.exists():
                with open(file_path, encoding='utf-8') as f:
                    content = f.read()

                # Find all ticket IDs
                id_pattern = r"ID: `([^`]+)`"
                for match in re.finditer(id_pattern, content):
                    ticket_id = match.group(1)
                    tickets.append(self._get_ticket(ticket_id))

                    if limit and len(tickets) >= limit:
                        return tickets

        return tickets

    def _search_tickets(self, query: str) -> list[TicketStatus]:
        """Search tickets by query in markdown files."""
        tickets = []
        query_lower = query.lower()

        for file_path in [self.changelog_path, self.todo_path]:
            if file_path.exists():
                with open(file_path, encoding='utf-8') as f:
                    content = f.read()

                # Find sections containing the query
                sections = re.split(r"## ", content)[1:]  # Skip header

                for section in sections:
                    if query_lower in section.lower():
                        # Extract ticket ID
                        id_match = re.search(r"ID: `([^`]+)`", section)
                        if id_match:
                            ticket_id = id_match.group(1)
                            tickets.append(self._get_ticket(ticket_id))

        return tickets
