"""Canonical project-root discovery for Planfile stores."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import yaml

from planfile.utils.repository import normalize_repository
from planfile.utils.yaml_cache import read_yaml_file as _read_yaml_file

PLANFILE_DIRNAME = ".planfile"
OPERATIONAL_STORE_DIRNAME = "planfile-operational"
OPERATIONAL_RECEIPT_FILENAME = ".operational-store.json"

_TRUTHY_MODES = {"1", "true", "yes", "on", "operational"}
_FALSY_MODES = {"0", "false", "no", "off", "tracked"}


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


def resolve_git_common_dir(path: str | Path) -> Path | None:
    """Resolve the shared Git common directory across primary and linked worktrees."""
    target = Path(path).resolve()
    value = _git_value(target, "rev-parse", "--git-common-dir")
    if not value:
        return None
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (target / candidate).resolve()


def resolve_primary_project_root(path: str | Path) -> Path:
    """Return the canonical primary checkout root owning *path*."""
    target = Path(path).resolve()
    common_dir = resolve_git_common_dir(target)
    if common_dir is not None and common_dir.name == ".git":
        return common_dir.parent.resolve()
    return _git_root(target) or target


def _configured_operational_root_from_yaml(project_dir: Path) -> str | None:
    for root in dict.fromkeys((project_dir, resolve_primary_project_root(project_dir))):
        config_path = root / PLANFILE_DIRNAME / "config.yaml"
        try:
            data = _read_yaml_file(config_path) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        storage = data.get("storage")
        if isinstance(storage, dict) and storage.get("operational_store_root"):
            return str(storage["operational_store_root"]).strip()
    return None


def resolve_operational_base_dir(project_dir: str | Path) -> Path:
    """Return the repository-bound operational ``.planfile`` directory outside tracked source."""
    target = Path(project_dir).resolve()
    primary_root = resolve_primary_project_root(target)
    configured_root = (
        os.environ.get("PLANFILE_OPERATIONAL_STORE_ROOT", "").strip()
        or (_git_value(target, "config", "--get", "planfile.operationalStoreRoot") or "").strip()
        or _configured_operational_root_from_yaml(target)
    )
    if configured_root:
        raw = Path(configured_root).expanduser()
        resolved = raw.resolve() if raw.is_absolute() else (primary_root / raw).resolve()
        return resolved if resolved.name == PLANFILE_DIRNAME else resolved / PLANFILE_DIRNAME
    common_dir = resolve_git_common_dir(target)
    if common_dir is not None:
        return (common_dir / OPERATIONAL_STORE_DIRNAME / PLANFILE_DIRNAME).resolve()
    return (primary_root / ".subactor" / OPERATIONAL_STORE_DIRNAME / PLANFILE_DIRNAME).resolve()


def is_operational_store_enabled(project_dir: str | Path) -> bool:
    """Determine whether *project_dir* routes operational state outside tracked files."""
    target = Path(project_dir).resolve()
    for env_key in ("PLANFILE_OPERATIONAL_STORE", "PLANFILE_STORE_MODE"):
        env_val = os.environ.get(env_key, "").strip().lower()
        if env_val in _TRUTHY_MODES:
            return True
        if env_val in _FALSY_MODES:
            return False

    for git_key in ("planfile.operationalStore", "planfile.storeMode"):
        git_val = (_git_value(target, "config", "--get", git_key) or "").strip().lower()
        if git_val in _TRUTHY_MODES:
            return True
        if git_val in _FALSY_MODES:
            return False

    operational_dir = resolve_operational_base_dir(target)
    receipt_path = operational_dir / OPERATIONAL_RECEIPT_FILENAME
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            receipt = None
        if isinstance(receipt, dict) and isinstance(receipt.get("enabled"), bool):
            return bool(receipt["enabled"])

    for root in dict.fromkeys((target, resolve_primary_project_root(target))):
        config_path = root / PLANFILE_DIRNAME / "config.yaml"
        try:
            data = _read_yaml_file(config_path) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        storage = data.get("storage")
        if isinstance(storage, dict):
            if storage.get("operational_store") is True:
                return True
            if str(storage.get("mode") or "").strip().lower() == "operational":
                return True
    return False


def _configured_github_repository(project_path: Path) -> str | None:
    """Read the repository binding from the project-local integration config."""
    primary_root = resolve_primary_project_root(project_path)
    candidates = [
        project_path / "github.planfile.yaml",
        project_path / "integrations.oql.planfile.yaml",
        project_path / ".planfile" / "github.planfile.yaml",
        project_path / ".planfile" / "integrations.oql.planfile.yaml",
    ]
    if primary_root != project_path:
        candidates.extend(
            [
                primary_root / "github.planfile.yaml",
                primary_root / "integrations.oql.planfile.yaml",
                primary_root / ".planfile" / "github.planfile.yaml",
                primary_root / ".planfile" / "integrations.oql.planfile.yaml",
            ]
        )
    for config_path in candidates:
        try:
            data = _read_yaml_file(config_path) or {}
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


def _walk_for_repo_store(path: Path, start_root: Path) -> Path:
    cursor = path
    while True:
        candidate = cursor / PLANFILE_DIRNAME
        candidate_root = _git_root(cursor)
        if candidate.is_dir() and candidate_root in {None, start_root}:
            return cursor
        if cursor == cursor.parent or cursor == start_root:
            return path
        cursor = cursor.parent


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
        and (not start_root or _git_root(candidate) in {None, start_root})
    ]
    if same_repo_stores:
        project_root = same_repo_stores[-1].parent
    elif not start_root:
        project_root = path
    else:
        project_root = _walk_for_repo_store(path, start_root)
        if project_root == path and start_root != path and is_operational_store_enabled(start_root):
            project_root = start_root
    if (project_root / PLANFILE_DIRNAME).is_dir() or is_operational_store_enabled(project_root):
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
    "OPERATIONAL_RECEIPT_FILENAME",
    "OPERATIONAL_STORE_DIRNAME",
    "PLANFILE_DIRNAME",
    "RepositoryRoutingError",
    "canonical_project_root",
    "ensure_project_root",
    "is_operational_store_enabled",
    "resolve_git_common_dir",
    "resolve_operational_base_dir",
    "resolve_primary_project_root",
]
