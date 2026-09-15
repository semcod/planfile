"""Canonical project-root discovery for Planfile stores."""

from __future__ import annotations

from pathlib import Path

PLANFILE_DIRNAME = ".planfile"


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
    outer_store = _outermost_planfile_ancestor(path)
    return outer_store.parent if outer_store is not None else path


def ensure_project_root(directory: str | Path) -> Path:
    """Return a project root or reject an explicit path inside ``.planfile``."""
    path = Path(directory).resolve()
    if path.name == PLANFILE_DIRNAME or any(parent.name == PLANFILE_DIRNAME for parent in path.parents):
        raise ValueError(
            f"project_path_inside_planfile: {path}; pass the repository root instead",
        )
    return path


__all__ = ["PLANFILE_DIRNAME", "canonical_project_root", "ensure_project_root"]
