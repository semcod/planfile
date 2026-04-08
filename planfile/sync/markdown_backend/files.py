from __future__ import annotations

from pathlib import Path


class MarkdownFileManager:
    """File existence and bootstrap helpers for markdown ticket files."""

    def _ensure_files_exist(self) -> None:
        """Ensure markdown files exist with a basic structure."""
        if not self.changelog_path.exists():
            self.changelog_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.changelog_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
                )

        if not self.todo_path.exists():
            self.todo_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.todo_path, "w", encoding="utf-8") as f:
                f.write("# TODO\n\nTasks and improvements to be done.\n\n")


__all__ = ["MarkdownFileManager"]
