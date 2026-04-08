from __future__ import annotations

from pathlib import Path
from typing import Any

from planfile.sync.base import BasePMBackend, TicketRef, TicketStatus

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
        title: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TicketRef:
        target_file = self._determine_target_file(title, labels, body)
        if self._ticket_exists_by_title(title, target_file):
            raise ValueError(f"Ticket already exists: {title}")

        entry = self._format_ticket_entry(
            ticket_id="",
            title=title,
            body=body,
            labels=labels,
            priority=priority,
            assignee=assignee,
            metadata=metadata,
        )
        ticket_id = self._generate_ticket_id(title, target_file)
        entry = entry.replace("**ID:** ``", f"**ID:** `{ticket_id}`")
        self._write_ticket_to_file(entry, target_file)
        return self.build_ticket_ref(id=ticket_id, url=str(target_file), status="open")


__all__ = ["MarkdownFileBackend"]
