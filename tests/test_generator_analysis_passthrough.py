"""Regression tests for the from-files generator.

Three defects are covered here:
  1. generate_from_current_project discarded its own analysis by re-analyzing the
     .planfile_analysis temp dir, so every project produced an identical strategy
     named ".Planfile_Analysis Improvement Plan".
  2. analyze_directory descended into vendored trees (.venv, site-packages), so
     dependency code produced the project's critical/high tickets.
  3. `validate schema` judged a Strategy against the ticket-store schema.
"""

import json
import textwrap
from pathlib import Path

import pytest
import yaml

from planfile.analysis.file_analyzer import FileAnalyzer
from planfile.analysis.generator import PlanfileGenerator
from planfile.core.schema import detect_document_type, validate_yaml_file


def _project(root: Path, name: str, body: dict) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "config.yaml").write_text(yaml.safe_dump(body))
    return d


def test_strategy_name_comes_from_the_project_not_the_temp_dir(tmp_path):
    d = _project(tmp_path, "alpha", {"steps": ["one"]})
    s = PlanfileGenerator().generate_from_current_project(project_path=str(d))
    assert s["project_name"] == "alpha"
    assert ".planfile_analysis" not in s["name"].lower()


def test_two_projects_do_not_produce_identical_strategies(tmp_path):
    a = _project(tmp_path, "alpha", {"note": "clean config"})
    b = _project(tmp_path, "beta", {"note": "BUG: this one is broken", "hack": "FIXME later"})
    g = PlanfileGenerator()
    sa = g.generate_from_current_project(project_path=str(a))
    sb = g.generate_from_current_project(project_path=str(b))
    assert sa["project_name"] != sb["project_name"]
    assert sa != sb, "distinct projects must not yield a byte-identical strategy"


def test_explicit_project_name_still_wins(tmp_path):
    d = _project(tmp_path, "alpha", {"k": "v"})
    s = PlanfileGenerator().generate_from_current_project(project_path=str(d), project_name="custom")
    assert s["project_name"] == "custom"


def test_compact_mode_writes_no_artifact_into_the_project(tmp_path):
    d = _project(tmp_path, "alpha", {"k": "v"})
    PlanfileGenerator().generate_from_current_project(project_path=str(d), compact=True)
    assert not (d / ".planfile_analysis").exists()


def test_analysis_result_is_not_recomputed_when_supplied(tmp_path):
    d = _project(tmp_path, "alpha", {"k": "v"})
    g = PlanfileGenerator()
    calls = []
    original = g.analyzer.analyze_directory

    def counting(directory, patterns=None):
        calls.append(str(directory))
        return original(directory, patterns)

    g.analyzer.analyze_directory = counting
    g.generate_from_current_project(project_path=str(d))
    assert len(calls) == 1, f"analysis ran {len(calls)} times: {calls}"


@pytest.mark.parametrize("vendor", [".venv", "node_modules", "site-packages", "dist", "pkg.egg-info"])
def test_vendored_trees_are_not_analyzed(tmp_path, vendor):
    d = tmp_path / "alpha"
    (d / vendor / "deep").mkdir(parents=True)
    (d / "own.yaml").write_text(yaml.safe_dump({"note": "ok"}))
    (d / vendor / "deep" / "dep.yaml").write_text(yaml.safe_dump({"note": "BUG: vendored"}))
    result = FileAnalyzer().analyze_directory(d)
    assert any("own.yaml" in f for f in result["analyzed_files"])
    assert not any(vendor in f for f in result["analyzed_files"])


def test_project_living_under_an_excluded_name_is_still_analyzed(tmp_path):
    """Exclusions apply below the analysis root, not to the root's own ancestors."""
    d = tmp_path / "build" / "myproject"
    d.mkdir(parents=True)
    (d / "own.yaml").write_text(yaml.safe_dump({"note": "ok"}))
    result = FileAnalyzer().analyze_directory(d)
    assert any("own.yaml" in f for f in result["analyzed_files"])


def test_document_type_detection():
    assert detect_document_type({"schema": "1.1", "project": "x"}) == "planfile"
    assert detect_document_type({"sprint": {"id": 1}}) == "sprint"
    assert detect_document_type({"name": "S", "sprints": []}) == "strategy"
    assert detect_document_type({"name": "S", "quality_gates": []}) == "strategy"
    assert detect_document_type([]) == "unknown"


def test_generated_strategy_passes_schema_validation(tmp_path):
    d = _project(tmp_path, "alpha", {"k": "v"})
    s = PlanfileGenerator().generate_from_current_project(project_path=str(d))
    out = tmp_path / "strategy.yaml"
    out.write_text(yaml.safe_dump(s, sort_keys=False))
    ok, errors = validate_yaml_file(out, "auto")
    assert ok, errors


def test_ticket_store_planfile_still_validated_as_planfile(tmp_path):
    out = tmp_path / "planfile.yaml"
    out.write_text(yaml.safe_dump({"schema": "1.1", "project": "demo", "tasks": []}))
    ok, errors = validate_yaml_file(out, "auto")
    assert ok, errors
    out.write_text(yaml.safe_dump({"schema": "1.1", "project": "demo", "tasks": {}}))
    ok, errors = validate_yaml_file(out, "auto")
    assert not ok and any("tasks" in e for e in errors)
