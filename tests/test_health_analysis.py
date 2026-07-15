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


def test_health_cache_reports_ok_with_no_planfile_dir(tmp_path):
    result = CliRunner().invoke(app, ["health", "cache", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No .planfile/" in result.output


def test_health_cache_heals_drift_and_exits_nonzero(tmp_path):
    import json

    from planfile.core import fastio

    base = tmp_path / ".planfile" / "sprints"
    base.mkdir(parents=True)
    y = base / "current.yaml"
    y.write_text("sprint:\n  tickets:\n    PLF-1:\n      name: a\n", encoding="utf-8")
    bad_payload = {"version": 1, "yaml_mtime_ns": y.stat().st_mtime_ns, "data": {}}
    fastio.mirror_path(y).write_text(json.dumps(bad_payload), encoding="utf-8")

    result = CliRunner().invoke(app, ["health", "cache", str(tmp_path)])

    assert result.exit_code == 1, result.output
    assert "1/1 cache mirror(s) drifted" in result.output
    assert "healed" in result.output

    healed = json.loads(fastio.mirror_path(y).read_text())
    assert healed["data"]["sprint"]["tickets"]["PLF-1"]["name"] == "a"


def test_health_cache_clean_project_exits_zero(tmp_path):
    from planfile.core import fastio

    base = tmp_path / ".planfile" / "sprints"
    base.mkdir(parents=True)
    y = base / "current.yaml"
    y.write_text("sprint:\n  tickets: {}\n", encoding="utf-8")
    fastio.read_yaml_fast(y)  # heals/creates a correct mirror

    result = CliRunner().invoke(app, ["health", "cache", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "cache OK" in result.output
