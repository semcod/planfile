from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from planfile.sync.base import BasePMBackend, TicketRef, TicketState

from .files import MarkdownFileManager
from .tickets import MarkdownTicketHelpers


class MarkdownFileBackend(MarkdownFileManager, MarkdownTicketHelpers, BasePMBackend):
    """Backend for managing tickets in CHANGELOG.md and TODO.md files."""

    def __init__(self, changelog_file: str = "CHANGELOG.md", todo_file: str = "TODO.md", **kwargs):
        config = {"changelog_file": changelog_file, "todo_file": todo_file, **kwargs}
        super().__init__(config)
        self.changelog_path = Path(self.config["changelog_file"])
        self.todo_path = Path(self.config["todo_file"])
        self._ensure_files_exist()

    def _create_ticket(
        self,
        name: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TicketRef:
        target_file = self._determine_target_file(name, labels, body)
        if self._ticket_exists_by_title(name, target_file):
            raise ValueError(f"Ticket already exists: {name}")

        entry = self._format_ticket_entry(
            ticket_id="",
            title=name,
            body=body,
            labels=labels,
            priority=priority,
            assignee=assignee,
            metadata=metadata,
        )
        ticket_id = self._generate_ticket_id(name, target_file)
        entry = entry.replace("**ID:** ``", f"**ID:** `{ticket_id}`")
        self._write_ticket_to_file(entry, target_file)
        return self.build_ticket_ref(id=ticket_id, url=str(target_file), status="open")

    def _update_ticket(
        self,
        ticket_id: str,
        name: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
    ) -> None:
        """Best-effort update for markdown tickets.

        For markdown backend we currently support existence check and no-op update.
        """
        _ = (name, body, status, labels, priority, assignee)
        location = self._find_ticket_file(ticket_id)
        if location is None:
            raise ValueError(f"Ticket not found: {ticket_id}")

    def _get_ticket(self, ticket_id: str) -> TicketState:
        """Get markdown ticket by ID."""
        location = self._find_ticket_file(ticket_id)
        if location is None:
            raise ValueError(f"Ticket not found: {ticket_id}")
        return self.build_ticket_state(id=ticket_id, status="open")

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
    ) -> list[TicketState]:
        """List markdown tickets by scanning TODO/CHANGELOG IDs."""
        _ = (labels, status, assignee)
        ticket_ids = self._scan_ticket_ids()
        if limit is not None and limit >= 0:
            ticket_ids = ticket_ids[:limit]
        return [self.build_ticket_state(id=ticket_id, status="open") for ticket_id in ticket_ids]

    def _search_tickets(self, query: str) -> list[TicketState]:
        """Search markdown tickets by ticket ID substring."""
        q = (query or "").lower()
        matches = [ticket_id for ticket_id in self._scan_ticket_ids() if q in ticket_id.lower()]
        return [self.build_ticket_state(id=ticket_id, status="open") for ticket_id in matches]

    def _find_ticket_file(self, ticket_id: str) -> Path | None:
        """Find file containing a given markdown ticket ID."""
        for path in (self.todo_path, self.changelog_path):
            if not path.exists():
                continue
            if ticket_id in path.read_text(encoding="utf-8"):
                return path
        return None

    def _scan_ticket_ids(self) -> list[str]:
        """Extract ticket IDs from markdown files."""
        ids: list[str] = []
        seen: set[str] = set()
        pattern = re.compile(r"\*\*ID:\*\*\s*`([^`]+)`")

        for path in (self.todo_path, self.changelog_path):
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            for ticket_id in pattern.findall(content):
                if ticket_id in seen:
                    continue
                ids.append(ticket_id)
                seen.add(ticket_id)

        return ids


__all__ = ["MarkdownFileBackend"]
