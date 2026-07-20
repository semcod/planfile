from __future__ import annotations

import subprocess
import sys

from typer.testing import CliRunner

from planfile.cli.commands import app


def test_planfile_without_command_shows_help() -> None:
    result = CliRunner().invoke(app, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Commands" in result.output
    assert "Missing command" not in result.output


def test_python_dash_m_planfile_runs_cli() -> None:
    """``python -m planfile`` must invoke the CLI (regression: missing __main__.py)."""
    result = subprocess.run(
        [sys.executable, "-m", "planfile", "--version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "version" in result.stdout.lower()


def test_auto_loop_command_matches_documented_cli() -> None:
    result = CliRunner().invoke(app, ["auto", "loop", "--help"])

    assert result.exit_code == 0
    assert "Run automated CI/CD loop" in result.output


def test_legacy_auto_loop_alias_remains_available() -> None:
    result = CliRunner().invoke(app, ["auto", "auto-loop", "--help"])

    assert result.exit_code == 0
    assert "Run automated CI/CD loop" in result.output
