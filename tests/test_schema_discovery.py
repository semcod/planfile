"""Repository-bounded schema document discovery regressions."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from planfile.cli.commands import app
from planfile.core.schema import validate_yaml_file


def _write_config(path: Path, project: str = "demo") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"project": project, "prefix": "PLF", "next_id": 1}),
        encoding="utf-8",
    )


def test_local_config_wins_over_legacy_document(tmp_path, monkeypatch):
    _write_config(tmp_path / ".planfile" / "config.yaml")
    (tmp_path / "planfile.yaml").write_text(
        "schema: '1.1'\nproject: legacy\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["validate", "schema"])

    assert result.exit_code == 0, result.output
    assert "type: config" in result.output
    assert "planfile.yaml" not in result.output
    assert validate_yaml_file(tmp_path / ".planfile" / "config.yaml", "config") == (True, [])


def test_parent_global_config_is_not_selected_or_mutated(tmp_path, monkeypatch):
    parent_config = tmp_path / ".planfile" / "config.yaml"
    _write_config(parent_config, project="global")
    child = tmp_path / "child"
    child.mkdir()
    before = parent_config.read_bytes()
    monkeypatch.chdir(child)

    result = CliRunner().invoke(app, ["validate", "schema"])

    assert result.exit_code == 1
    assert "refusing to use a parent or global" in result.output
    assert parent_config.read_bytes() == before
    assert not (child / ".planfile").exists()


def test_root_legacy_planfile_remains_supported(tmp_path, monkeypatch):
    legacy = tmp_path / "planfile.yaml"
    legacy.write_text("schema: '1.1'\nproject: legacy\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["validate", "schema"])

    assert result.exit_code == 0
    assert str(legacy) in result.output
    assert "Schema validation passed" in result.output


def test_no_local_document_fails_closed_without_creating_store(tmp_path, monkeypatch):
    child = tmp_path / "nested"
    child.mkdir()
    monkeypatch.chdir(child)

    result = CliRunner().invoke(app, ["validate", "schema"])

    assert result.exit_code == 1
    assert "No repository-local schema document found" in result.output
    assert not (child / ".planfile").exists()
