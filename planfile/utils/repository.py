"""Canonical identity of a GitHub-style repository (``owner/name``).

Foundation helper: depends on nothing in planfile, so path discovery and sync can both use it
without the foundation layer importing the sync layer.
"""

from __future__ import annotations

import re

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SCP_PREFIX = "git@github.com:"
_URL_PREFIXES = ("https://github.com/", "http://github.com/", "ssh://git@github.com/")


def normalize_repository(value: str | None) -> str | None:
    """Return a stable ``owner/name`` identity for GitHub-style repositories."""
    if value is None:
        return None
    candidate = str(value).strip()
    if candidate.lower().startswith(_SCP_PREFIX):
        candidate = candidate[len(_SCP_PREFIX) :]
    for prefix in _URL_PREFIXES:
        if candidate.lower().startswith(prefix):
            candidate = candidate[len(prefix) :]
            break
    candidate = candidate.removesuffix("/").removesuffix(".git")
    if not _REPOSITORY.fullmatch(candidate):
        raise ValueError("invalid repository identity; expected owner/name")
    owner, name = candidate.split("/", 1)
    return f"{owner.lower()}/{name.lower()}"
