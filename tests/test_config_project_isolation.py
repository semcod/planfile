"""Regression tests for explicit repository-local configuration routing."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from planfile import Planfile
from planfile.cli.commands import app


def test_explicit_project_config_does_not_mutate_parent(tmp_path: Path):
    parent = tmp_path / "parent"
    child = parent / "child"
    Planfile(str(parent))

    result = CliRunner().invoke(
        app,
        [
            "config",
            "set",
            "integrations.github.repo",
            "child/repository",
            "--project",
            str(child),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    child_overlay = child / ".planfile" / "integrations.oql.planfile.yaml"
    assert yaml.safe_load(child_overlay.read_text(encoding="utf-8"))["integrations"]["github"]["repo"] == "child/repository"
    assert not (parent / ".planfile" / "integrations.oql.planfile.yaml").exists()
