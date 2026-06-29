from __future__ import annotations

from typer.testing import CliRunner

from planfile.analysis.parsers.text_parser import analyze_text
from planfile.cli.commands import app


def test_text_parser_uses_issue_name(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("TODO: document the next release\n", encoding="utf-8")

    issues, metrics, tasks = analyze_text(readme)

    assert issues
    assert issues[0].name.startswith("Todo:")
    assert issues[0].description == "document the next release"
    assert metrics == []
    assert tasks == []


def test_health_check_handles_generated_ticket_buckets(tmp_path):
    (tmp_path / "README.md").write_text("TODO: document health output\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["health", "check", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Health Metrics" in result.output
    assert "Error analyzing project" not in result.output
