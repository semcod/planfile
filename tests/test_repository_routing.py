from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

import planfile
from planfile.cli.groups.sync import core as sync_core
from planfile.cli.groups.ticket import commands
from planfile.integrations.config import IntegrationConfig
from planfile.project_paths import RepositoryRoutingError


def _git_repo(path: Path, origin: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin], check=True)


def _github_config(path: Path, repo: str) -> None:
    config_dir = path / ".planfile"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "integrations.oql.planfile.yaml").write_text(
        f"integrations:\n  github:\n    repo: {repo}\n",
        encoding="utf-8",
    )


def test_auto_discover_uses_nearest_store_in_same_repository(tmp_path: Path) -> None:
    root = tmp_path / "parent"
    _git_repo(root, "git@github.com:owner/parent.git")
    _github_config(root, "owner/parent")
    child = root / "src" / "service"
    child.mkdir(parents=True)

    discovered = planfile.Planfile.auto_discover(str(child))

    assert discovered.store.project_dir == root.resolve()


def test_canonical_root_does_not_cross_nested_repository_boundary(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    _git_repo(parent, "git@github.com:owner/parent.git")
    _github_config(parent, "owner/parent")
    nested = parent / "nested"
    _git_repo(nested, "git@github.com:owner/nested.git")

    from planfile.project_paths import canonical_project_root

    assert canonical_project_root(nested) == nested.resolve()


def test_auto_discover_does_not_cross_nested_repository_boundary(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    _git_repo(parent, "git@github.com:owner/parent.git")
    _github_config(parent, "owner/parent")
    nested = parent / "nested"
    _git_repo(nested, "git@github.com:owner/nested.git")

    discovered = planfile.Planfile.auto_discover(str(nested))

    assert discovered.store.project_dir == nested.resolve()
    assert (nested / ".planfile" / "config.yaml").exists()
    assert (parent / ".planfile" / "integrations.oql.planfile.yaml").exists()


def test_auto_discover_rejects_configured_origin_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _git_repo(root, "git@github.com:owner/actual.git")
    _github_config(root, "owner/expected")

    with pytest.raises(RepositoryRoutingError, match="does not match"):
        planfile.Planfile.auto_discover(str(root))


def test_auto_sync_forwards_exact_scope(monkeypatch, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(IntegrationConfig, "load_configs", lambda self: None)

    def fake_sync(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(sync_core, "sync_integration", fake_sync)

    commands._auto_sync(
        str(tmp_path),
        integrations=["github"],
        ticket_ids=["PLF-9"],
        sprint_ids=["custom-review"],
    )

    assert calls == [
        (
            ("github", str(tmp_path), False, "to"),
            {
                "show_header": False,
                "ticket_ids": ["PLF-9"],
                "sprint_ids": ["custom-review"],
            },
        )
    ]


def test_auto_sync_failure_is_nonzero(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(IntegrationConfig, "load_configs", lambda self: None)

    def failing_sync(*args, **kwargs):
        raise RuntimeError("controlled failure")

    monkeypatch.setattr(sync_core, "sync_integration", failing_sync)

    with pytest.raises(typer.Exit) as error:
        commands._auto_sync(str(tmp_path), integrations=["github"], ticket_ids=["PLF-9"])

    assert error.value.exit_code == 1
