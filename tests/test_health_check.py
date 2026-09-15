from __future__ import annotations

import json
import time

from typer.testing import CliRunner

from planfile.analysis.file_analyzer import FileAnalyzer
from planfile.analysis.parsers.yaml_parser import analyze_yaml
from planfile.cli.commands import app


def test_github_workflow_yaml_on_key_and_expressions_are_supported(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """name: CI
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo \"${{ github.sha }}\"
""",
        encoding="utf-8",
    )

    issues, _metrics, _tasks = analyze_yaml(workflow)

    assert not any("Failed to parse" in issue.name for issue in issues)
    assert not any("bool" in issue.description for issue in issues)


def test_invalid_github_workflow_reports_one_precise_diagnostic(tmp_path):
    workflow = tmp_path / ".github" / "workflows" / "broken.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: CI\non: [push\n", encoding="utf-8")

    issues, _metrics, _tasks = analyze_yaml(workflow)

    diagnostics = [issue for issue in issues if "Unsupported GitHub Actions YAML" in issue.name]
    assert len(diagnostics) == 1
    assert "Unsupported GitHub Actions YAML construct" in diagnostics[0].description
    assert not any("Failed to parse" in issue.name for issue in issues)


def test_analyzer_reports_budget_truncation(tmp_path):
    (tmp_path / "a.yml").write_text("name: a\n", encoding="utf-8")
    (tmp_path / "b.yml").write_text("name: b\n", encoding="utf-8")

    result = FileAnalyzer().analyze_directory(tmp_path, ["*.yml"], max_files=1)

    assert result["budget"] == {
        "max_files": 1,
        "max_bytes": None,
        "files": 1,
        "bytes": len("name: a\n"),
        "truncated": True,
    }


def test_health_json_is_read_only_and_reports_project(tmp_path):
    (tmp_path / "module.py").write_text("print('ok')\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["health", "check", str(tmp_path), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["project_path"] == str(tmp_path.resolve())
    assert payload["analysis"]["files"] == 1
    assert payload["limits"]["max_files"] == 5000
    assert payload["analysis"]["truncated"] is False
    assert payload["diagnostics"] == []
    assert not (tmp_path / ".planfile_analysis").exists()


def test_health_timeout_is_structured_and_nonzero(tmp_path, monkeypatch):
    def slow_analysis(*_args, **_kwargs):
        time.sleep(0.2)
        return {"summary": {}, "budget": {}, "issues": []}

    monkeypatch.setattr(FileAnalyzer, "analyze_directory", slow_analysis)
    result = CliRunner().invoke(
        app,
        ["health", "check", str(tmp_path), "--timeout", "0.1", "--format", "json"],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "timeout"
    assert payload["diagnostics"][0]["code"] == "HEALTH_TIMEOUT"
    assert str(tmp_path.resolve()) in payload["diagnostics"][0]["message"]
