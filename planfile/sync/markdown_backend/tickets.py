from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


class MarkdownTicketHelpers:
    """Ticket routing, lookup, formatting, and persistence helpers."""

    def _determine_target_file(self, title: str, labels: list[str] | None, body: str) -> Path:
        changelog_keywords = ["release", "released", "completed", "fixed", "added", "removed", "changed"]
        todo_keywords = ["todo", "fix", "implement", "add", "update", "refactor"]

        title_lower = title.lower()
        body_lower = body.lower()

        if labels:
            if any(label.lower() in ["changelog", "release", "completed"] for label in labels):
                return self.changelog_path
            if any(label.lower() in ["todo", "task", "bug"] for label in labels):
                return self.todo_path

        if any(keyword in title_lower or keyword in body_lower for keyword in changelog_keywords):
            return self.changelog_path
        if any(keyword in title_lower or keyword in body_lower for keyword in todo_keywords):
            return self.todo_path

        return self.todo_path

    def _generate_ticket_id(self, title: str, target_file: Path) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", title).strip()
        slug = re.sub(r"[-\s]+", "-", slug)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{slug}-{timestamp}"

    def _ticket_exists(self, ticket_id: str, target_file: Path) -> bool:
        with open(target_file, encoding="utf-8") as f:
            return ticket_id in f.read()

    def _ticket_exists_by_title(self, title: str, target_file: Path) -> bool:
        if not target_file.exists():
            return False

        with open(target_file, encoding="utf-8") as f:
            content = f.read()

        pattern = rf"##\s+(?:[🔴🟠🟡🟢⚪]\s+)?{re.escape(title)}\s*$"
        for line in content.split("\n"):
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
        metadata: dict[str, Any] | None,
    ) -> str:
        lines = []
        priority_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }.get(priority, "⚪")

        lines.append(f"## {priority_emoji} {title}")
        lines.append("")
        lines.append(f"**ID:** `{ticket_id}`")
        if priority:
            lines.append(f"**Priority:** {priority}")
        if assignee:
            lines.append(f"**Assignee:** {assignee}")
        if labels:
            lines.append(f"**Labels:** {', '.join(labels)}")
        lines.append("")
        if body:
            lines.append(body)
            lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def _write_ticket_to_file(self, entry: str, target_file: Path) -> None:
        with open(target_file, "r+", encoding="utf-8") as f:
            content = f.read()
            if target_file.name == "CHANGELOG.md":
                header_end = content.find("\n\n", content.find("# Changelog"))
                if header_end == -1:
                    header_end = content.find("\n", content.find("# Changelog"))
                insert_pos = header_end + 2 if header_end > 0 else len(content)
            else:
                header_end = content.find("\n\n", content.find("# TODO"))
                if header_end == -1:
                    header_end = content.find("\n", content.find("# TODO"))
                insert_pos = header_end + 2 if header_end > 0 else len(content)

            new_content = content[:insert_pos] + entry + content[insert_pos:]
            f.seek(0)
            f.write(new_content)
            f.truncate()


__all__ = ["MarkdownTicketHelpers"]
