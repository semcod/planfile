"""Foundation helpers stay dependency-free and keep their callers' behavior."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from planfile import project_paths
from planfile.sync import state
from planfile.utils.repository import normalize_repository
from planfile.utils.yaml_cache import _load_yaml_cached, read_yaml_file

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("raw", [
    "owner/repo", "Owner/Repo", "https://github.com/Owner/Repo.git", "HTTP://GITHUB.COM/owner/repo/",
    "git@github.com:Owner/Repo.git", "ssh://git@github.com/Owner/Repo", "  owner/repo  ",
])
def test_normalize_repository_accepts_github_forms(raw):
    assert normalize_repository(raw) == "owner/repo"


@pytest.mark.parametrize("raw", ["", "owner", "owner/repo/extra", "https://gitlab.com/o/r", "o w/r"])
def test_normalize_repository_rejects_non_identities(raw):
    with pytest.raises(ValueError):
        normalize_repository(raw)


def test_normalize_repository_passes_none_through():
    assert normalize_repository(None) is None


def test_callers_share_one_implementation():
    assert state.normalize_repository is normalize_repository
    assert project_paths.normalize_repository is normalize_repository
    assert state._read_yaml_file is read_yaml_file is project_paths._read_yaml_file


def test_read_yaml_file_caches_until_the_file_changes(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("a: 1\n")
    _load_yaml_cached.cache_clear()
    assert read_yaml_file(path) == {"a": 1}
    assert read_yaml_file(path) == {"a": 1}
    assert _load_yaml_cached.cache_info().hits == 1
    stat = path.stat()
    path.write_text("a: 2\n")
    import os
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert read_yaml_file(path) == {"a": 2}


def _planfile_imports(module: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("planfile"):
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names if alias.name.startswith("planfile"))
    return names


@pytest.mark.parametrize("module", ["planfile/utils/repository.py", "planfile/utils/yaml_cache.py"])
def test_helpers_import_nothing_from_planfile(module):
    assert _planfile_imports(ROOT / module) == set()


def test_project_paths_no_longer_reaches_into_sync():
    """Foundation must not depend on the sync layer, not even through a function-level import."""
    assert not any(name.startswith("planfile.sync") for name in _planfile_imports(ROOT / "planfile/project_paths.py"))
