"""Git author detection from git config."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _detect_git_authors(project_path: Path) -> list[str]:
    """Detect authors from git config."""
    authors = []

    try:
        # Try to get user name and email from git config
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            cwd=project_path
        )
        if result.returncode == 0:
            name = result.stdout.strip()

            result = subprocess.run(
                ["git", "config", "user.email"],
                capture_output=True,
                text=True,
                cwd=project_path
            )
            if result.returncode == 0:
                email = result.stdout.strip()
                authors.append(f"{name} <{email}>")
    except Exception:
        pass

    return authors
