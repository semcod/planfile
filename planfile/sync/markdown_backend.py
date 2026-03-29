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
        """Update an existing ticket in the markdown files.
        
        Supports both structured format and checkbox-style tickets.
        """
        # Check if it's a checkbox-style ticket
        if re.match(r'^\w+-\d+-[a-f0-9]{8}$', ticket_id):
            if status:
                # Handle status update for checkbox
                completed = status.lower() in ['completed', 'done', 'closed', 'resolved']
                if self._toggle_checkbox_status(ticket_id, completed):
                    return
            # If status not provided or toggle failed, fall through to regular handling
            raise ValueError(f"Cannot update checkbox ticket {ticket_id} - only status changes supported")

        # Find which file contains the ticket (structured format)
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
        """Find which file contains the given ticket ID.
        
        Handles both structured tickets (with ID in content) and checkbox-style tickets.
        """
        for file_path in [self.changelog_path, self.todo_path]:
            if not file_path.exists():
                continue
                
            with open(file_path, encoding='utf-8') as f:
                content = f.read()
                
            # Check for structured ticket ID in content
            if f"ID: `{ticket_id}`" in content:
                return file_path
                
            # Check for checkbox-style ticket by pattern matching
            if re.match(r'^\w+-\d+-[a-f0-9]{8}$', ticket_id):
                # Parse line number from ticket ID
                parts = ticket_id.rsplit('-', 1)
                if len(parts) == 2:
                    prefix, _ = parts
                    try:
                        line_num = int(prefix.split('-')[-1])
                        lines = content.split('\n')
                        if 1 <= line_num <= len(lines):
                            line = lines[line_num - 1]
                            # Check if line is a checkbox
                            if re.match(r'^\s*-\s*\[[ xX]\]', line):
                                return file_path
                    except (ValueError, IndexError):
                        pass
                        
        return None

    def _generate_checkbox_ticket_id(self, content: str, file_path: Path, line_num: int) -> str:
        """Generate a unique ticket ID for checkbox-style tickets.
        
        Creates a stable ID based on file path, line number, and content hash.
        """
        import hashlib
        
        # Create a stable hash from content (first 50 chars)
        content_hash = hashlib.md5(content[:50].encode()).hexdigest()[:8]
        file_slug = re.sub(r'[^a-zA-Z0-9]', '-', file_path.stem)
        return f"{file_slug}-{line_num}-{content_hash}"

    def _get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get ticket status from markdown files.
        
        Handles both structured format (ID: `...`) and checkbox format (- [ ] / - [x]).
        """
        target_file = self._find_ticket_file(ticket_id)
        if not target_file:
            raise ValueError(f"Ticket not found: {ticket_id}")

        with open(target_file, encoding='utf-8') as f:
            content = f.read()

        # Check if it's a checkbox-style ticket (pattern: file-line-hash)
        if re.match(r'^\w+-\d+-[a-f0-9]{8}$', ticket_id):
            # Find the checkbox line by line number from ID
            parts = ticket_id.rsplit('-', 1)
            if len(parts) == 2:
                prefix, _ = parts
                try:
                    line_num = int(prefix.split('-')[-1])
                    lines = content.split('\n')
                    if 1 <= line_num <= len(lines):
                        line = lines[line_num - 1]
                        # Check if it's checked
                        is_checked = re.match(r'^\s*-\s*\[[xX]\]', line) is not None
                        status = "completed" if is_checked else "open"
                        return self.build_ticket_status(
                            id=ticket_id,
                            status=status,
                            updated_at=None
                        )
                except (ValueError, IndexError):
                    pass

        # Default: structured ticket (assumes open if found)
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
        """List tickets from markdown files.
        
        Supports both structured format (with ID: `...`) and checkbox format (- [ ] / - [x]).
        """
        tickets = []

        for file_path in [self.changelog_path, self.todo_path]:
            if file_path.exists():
                with open(file_path, encoding='utf-8') as f:
                    content = f.read()

                # Find all structured tickets with IDs
                id_pattern = r"ID: `([^`]+)`"
                for match in re.finditer(id_pattern, content):
                    ticket_id = match.group(1)
                    tickets.append(self._get_ticket(ticket_id))

                    if limit and len(tickets) >= limit:
                        return tickets

                # Find all checkbox-style tickets (- [ ] or - [x])
                checkbox_pattern = r"^\s*-\s*\[([ xX])\]\s*(.+)$"
                for line_num, line in enumerate(content.split('\n'), 1):
                    match = re.match(checkbox_pattern, line)
                    if match:
                        is_checked = match.group(1).lower() == 'x'
                        ticket_content = match.group(2).strip()
                        ticket_id = self._generate_checkbox_ticket_id(ticket_content, file_path, line_num)
                        ticket_status = "completed" if is_checked else "open"
                        
                        tickets.append(self.build_ticket_status(
                            id=ticket_id,
                            status=ticket_status,
                            updated_at=None
                        ))

                        if limit and len(tickets) >= limit:
                            return tickets

        return tickets

    def _search_tickets(self, query: str) -> list[TicketStatus]:
        """Search tickets by query in markdown files.
        
        Searches both structured format and checkbox-style tickets.
        """
        tickets = []
        query_lower = query.lower()

        for file_path in [self.changelog_path, self.todo_path]:
            if file_path.exists():
                with open(file_path, encoding='utf-8') as f:
                    content = f.read()

                # Find sections containing the query (structured format)
                sections = re.split(r"## ", content)[1:]  # Skip header

                for section in sections:
                    if query_lower in section.lower():
                        # Extract ticket ID
                        id_match = re.search(r"ID: `([^`]+)`", section)
                        if id_match:
                            ticket_id = id_match.group(1)
                            tickets.append(self._get_ticket(ticket_id))

                # Search checkbox-style tickets
                checkbox_pattern = r"^\s*-\s*\[([ xX])\]\s*(.+)$"
                for line_num, line in enumerate(content.split('\n'), 1):
                    match = re.match(checkbox_pattern, line)
                    if match and query_lower in line.lower():
                        is_checked = match.group(1).lower() == 'x'
                        ticket_content = match.group(2).strip()
                        ticket_id = self._generate_checkbox_ticket_id(ticket_content, file_path, line_num)
                        ticket_status = "completed" if is_checked else "open"
                        
                        tickets.append(self.build_ticket_status(
                            id=ticket_id,
                            status=ticket_status,
                            updated_at=None
                        ))

        return tickets

    def _toggle_checkbox_status(self, ticket_id: str, completed: bool) -> bool:
        """Toggle the status of a checkbox-style ticket.
        
        Args:
            ticket_id: The ticket ID (format: file-line-hash)
            completed: True to check [x], False to uncheck [ ]
            
        Returns:
            True if successful, False otherwise
        """
        # Parse ticket ID to get line number
        if not re.match(r'^\w+-\d+-[a-f0-9]{8}$', ticket_id):
            return False
            
        target_file = self._find_ticket_file(ticket_id)
        if not target_file:
            return False
            
        try:
            parts = ticket_id.rsplit('-', 1)
            prefix, _ = parts
            line_num = int(prefix.split('-')[-1])
            
            with open(target_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            if not (1 <= line_num <= len(lines)):
                return False
                
            line_idx = line_num - 1
            line = lines[line_idx]
            
            # Check if it's a checkbox line (with or without trailing newline in pattern)
            checkbox_match = re.match(r'^(\s*-\s*\[)([ xX])(\]\s*.+?)(\r?\n)?$', line)
            if not checkbox_match:
                return False
                
            # Replace checkbox status
            new_mark = 'x' if completed else ' '
            new_line = f"{checkbox_match.group(1)}{new_mark}{checkbox_match.group(3)}\n"
            lines[line_idx] = new_line
            
            with open(target_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            return True
            
        except (ValueError, IndexError, IOError):
            return False
