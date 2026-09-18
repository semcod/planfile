"""Canonical project-root discovery for Planfile stores."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

PLANFILE_DIRNAME = ".planfile"


class RepositoryRoutingError(RuntimeError):
    """Raised when discovery would cross or misidentify a Git repository."""


def _git_value(path: Path, *args: str) -> str | None:
    """Read one Git value without changing the checkout."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _git_root(path: Path) -> Path | None:
    value = _git_value(path, "rev-parse", "--show-toplevel")
    return Path(value).resolve() if value else None


def _configured_github_repository(project_path: Path) -> str | None:
    """Read the repository binding from the project-local integration config."""
    from planfile.sync.state import normalize_repository

    for config_path in (
        project_path / "github.planfile.yaml",
        project_path / "integrations.oql.planfile.yaml",
        project_path / ".planfile" / "github.planfile.yaml",
        project_path / ".planfile" / "integrations.oql.planfile.yaml",
    ):
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        integrations = data.get("integrations")
        section = integrations.get("github") if isinstance(integrations, dict) else None
        if section is None:
            section = data.get("github")
        if not isinstance(section, dict) or not section.get("repo"):
            continue
        try:
            return normalize_repository(str(section["repo"]))
        except ValueError as error:
            raise RepositoryRoutingError(
                f"invalid integrations.github.repo in {config_path}"
            ) from error
    return None


def _validate_repository_origin(project_path: Path) -> None:
    """Fail closed when a configured GitHub repository differs from origin."""
    configured = _configured_github_repository(project_path)
    origin = _git_value(project_path, "remote", "get-url", "origin")
    if not configured or not origin:
        return
    from planfile.sync.state import normalize_repository

    try:
        actual = normalize_repository(origin)
    except ValueError:
        raise RepositoryRoutingError(
            f"cannot normalize Git origin {origin!r} for configured {configured}"
        ) from None
    if actual != configured:
        raise RepositoryRoutingError(
            f"repository origin {actual} does not match integrations.github.repo {configured}"
        )


def _outermost_planfile_ancestor(path: Path) -> Path | None:
    """Return the farthest ``.planfile`` ancestor of *path*, if any."""
    ancestors = [candidate for candidate in (path, *path.parents) if candidate.name == PLANFILE_DIRNAME]
    return ancestors[-1] if ancestors else None


def canonical_project_root(start: str | Path) -> Path:
    """Resolve a path inside a Planfile store to its owning project root.

    Starting a command below ``.planfile`` is common for shell agents and
    linked checkouts. Walking from that directory used to discover a nested
    ``.planfile/.planfile`` store and write tickets into the wrong project.
    Anchor discovery at the project containing the outermost store instead.
    """
    path = Path(start).resolve()
    start_root = _git_root(path)
    same_repo_stores = [
        candidate
        for candidate in (path, *path.parents)
        if candidate.name == PLANFILE_DIRNAME
        and (
            not start_root
            or _git_root(candidate) in {None, start_root}
        )
    ]
    if same_repo_stores:
        project_root = same_repo_stores[-1].parent
    elif not start_root:
        # Without a Git boundary, an ancestor .planfile may belong to a
        # different project (for example /tmp/.planfile or ~/.planfile).
        # Only an explicit store path handled above is safe to adopt.
        project_root = path
    else:
        project_root = path
        cursor = path
        while True:
            candidate = cursor / PLANFILE_DIRNAME
            candidate_root = _git_root(cursor)
            if candidate.is_dir() and (
                not start_root or candidate_root in {None, start_root}
            ):
                project_root = cursor
                break
            if cursor == cursor.parent or (start_root and cursor == start_root):
                break
            cursor = cursor.parent
    if (project_root / PLANFILE_DIRNAME).is_dir():
        _validate_repository_origin(project_root)
    return project_root


def ensure_project_root(directory: str | Path) -> Path:
    """Return a project root or reject an explicit path inside ``.planfile``."""
    path = Path(directory).resolve()
    if path.name == PLANFILE_DIRNAME or any(parent.name == PLANFILE_DIRNAME for parent in path.parents):
        raise ValueError(
            f"project_path_inside_planfile: {path}; pass the repository root instead",
        )
    return path


__all__ = [
    "PLANFILE_DIRNAME",
    "RepositoryRoutingError",
    "canonical_project_root",
    "ensure_project_root",
]
