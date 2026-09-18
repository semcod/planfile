from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from planfile import Planfile
from planfile.core.store import PlanfileStore
from planfile.project_paths import canonical_project_root, ensure_project_root


def _git_init(path: Path) -> None:
    # canonical_project_root only bounds its upward walk for an ancestor
    # .planfile store when the start path is inside a Git repo. Without this,
    # a stray store above /tmp (e.g. /tmp/.planfile, ~/.planfile) on the host
    # machine silently wins over tmp_path, which is what this suite exists to
    # rule out — see ticket-129.
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def test_discovery_from_inside_store_uses_outer_project(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".planfile" / "sprints").mkdir(parents=True)
    (root / ".planfile" / "config.yaml").write_text("project: repo\n", encoding="utf-8")
    nested = root / ".planfile" / ".planfile" / "config.yaml"
    nested.parent.mkdir(parents=True)
    nested.write_text("project: nested\n", encoding="utf-8")

    discovered = Planfile.auto_discover(str(root / ".planfile" / "sprints"))

    assert discovered.store.project_dir == root.resolve()
    assert not (root / ".planfile" / ".planfile" / "sprints").exists()


def test_auto_discover_initialises_at_repository_root_when_store_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    inside_future_store = root / ".planfile" / "sprints"
    inside_future_store.mkdir(parents=True)

    discovered = Planfile.auto_discover(str(inside_future_store))

    assert discovered.store.project_dir == root.resolve()
    assert (root / ".planfile" / "config.yaml").exists()
    assert not (root / ".planfile" / ".planfile").exists()


def test_explicit_store_path_is_rejected_instead_of_nested_initialisation(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    store_path = root / ".planfile"
    store_path.mkdir(parents=True)

    with pytest.raises(ValueError, match="project_path_inside_planfile"):
        Planfile(str(store_path))
    with pytest.raises(ValueError, match="project_path_inside_planfile"):
        PlanfileStore(str(store_path / "sprints"))


def test_path_helpers_leave_normal_project_paths_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _git_init(root)
    (root / "src").mkdir()

    assert canonical_project_root(root / "src") == (root / "src").resolve()
    assert ensure_project_root(root) == root.resolve()
