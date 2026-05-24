from __future__ import annotations

from typer.testing import CliRunner

from planfile.cli.commands import app


def test_planfile_without_command_shows_help() -> None:
    result = CliRunner().invoke(app, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Commands" in result.output
    assert "Missing command" not in result.output
