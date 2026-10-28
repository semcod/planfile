"""Safe accelerated YAML analysis retains the pure loader's observable meaning."""

from dataclasses import asdict

import pytest
import yaml

from planfile.analysis.parsers import yaml_parser

VALID_DOCUMENTS = [
    "message: a bug needs fixing\non: failed\nyes: off\n",
    'quoted: "error with ☃ and café"\nnumber: 012\nnull_value: null\n',
    "defaults: &defaults\n  message: bug in defaults\ncopy:\n  <<: *defaults\n  other: issue in copy\n",
    "values: &values [bug, error]\ncopy: *values\n",
    "message: |\n  error on first line\n  bug on second line\n",
    "message: old error\nmessage: replacement bug\n",
    "date: 2026-10-28\ntruth: true\nfloat: 1.5\n",
    "recursive: &recursive {child: *recursive, message: error in cycle}\n",
]


def records(result):
    return [[asdict(row) for row in rows] for rows in result]


@pytest.mark.parametrize("content", VALID_DOCUMENTS)
def test_accelerated_loader_preserves_safe_yaml_analysis(tmp_path, monkeypatch, content):
    source = tmp_path / "sample.yaml"
    source.write_text(content, encoding="utf-8")
    monkeypatch.setattr(yaml_parser, "FastLoader", yaml.SafeLoader)
    expected = records(yaml_parser.analyze_yaml(source))
    monkeypatch.setattr(yaml_parser, "FastLoader", getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    assert records(yaml_parser.analyze_yaml(source)) == expected


@pytest.mark.parametrize("loader", [yaml.SafeLoader, getattr(yaml, "CSafeLoader", yaml.SafeLoader)])
@pytest.mark.parametrize("workflow", [False, True])
def test_unsafe_yaml_tags_never_execute(tmp_path, monkeypatch, loader, workflow):
    folder = tmp_path / ".github/workflows" if workflow else tmp_path
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "unsafe.yaml"
    marker = tmp_path / "must-not-exist"
    source.write_text(
        '!!python/object/apply:os.system ["touch ' + str(marker) + '"]\n', encoding="utf-8"
    )
    monkeypatch.setattr(yaml_parser, "FastLoader", loader)
    issues, _metrics, _tasks = yaml_parser.analyze_yaml(source)
    assert not marker.exists()
    if not workflow:
        assert any("Fix YAML syntax" in issue.name for issue in issues)


@pytest.mark.parametrize("loader", [yaml.SafeLoader, getattr(yaml, "CSafeLoader", yaml.SafeLoader)])
def test_malformed_workflow_retains_one_diagnostic(tmp_path, monkeypatch, loader):
    source = tmp_path / ".github/workflows/broken.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("name: CI\non: [push\n", encoding="utf-8")
    monkeypatch.setattr(yaml_parser, "FastLoader", loader)
    issues, metrics, tasks = yaml_parser.analyze_yaml(source)
    assert len(issues) == 1 and not metrics and not tasks
    assert issues[0].tags == ["yaml", "github-actions", "unsupported"]
    assert "Unsupported GitHub Actions YAML construct" in issues[0].description


def test_large_yaml_analysis_preserves_every_issue(tmp_path, monkeypatch):
    source = tmp_path / "large.yaml"
    source.write_text("\n".join(f"item_{i}: error number {i}" for i in range(1200)) + "\n")
    monkeypatch.setattr(yaml_parser, "FastLoader", yaml.SafeLoader)
    expected = records(yaml_parser.analyze_yaml(source))
    monkeypatch.setattr(yaml_parser, "FastLoader", getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    assert records(yaml_parser.analyze_yaml(source)) == expected
    assert len(expected[0]) >= 1200


@pytest.mark.parametrize(
    "content", ["poor: > 10s\n", "value: [broken\n", "value: !unknown input\n"]
)
def test_parser_error_diagnostics_match_the_pure_loader(tmp_path, monkeypatch, content):
    source = tmp_path / "invalid.yaml"
    source.write_text(content)
    monkeypatch.setattr(yaml_parser, "FastLoader", yaml.SafeLoader)
    expected = records(yaml_parser.analyze_yaml(source))
    monkeypatch.setattr(yaml_parser, "FastLoader", getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    assert records(yaml_parser.analyze_yaml(source)) == expected
