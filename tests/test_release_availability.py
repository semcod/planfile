from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("release_availability", Path(__file__).parents[1] / "planfile/release_availability.py")
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


def test_release_metadata_matches_published_offline_snapshot():
    result = CHECKER.check(Path(__file__).parents[1], offline=True)
    assert result["ok"] is True
    assert result["source_version"] == "0.1.126"


def test_newer_source_version_is_rejected(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "planfile"\nversion = "0.1.127"\nrequires-python = ">=3.10"\n')
    (tmp_path / "planfile").mkdir()
    metadata = {"package": "planfile", "source": {"version": "0.1.127"}, "runtime": {"version": "0.1.127", "python_requires": ">=3.10"}, "published": {"index": "unused", "version": "0.1.126", "python_requires": ">=3.10"}}
    (tmp_path / "planfile/release-metadata.json").write_text(json.dumps(metadata))
    result = CHECKER.check(tmp_path, offline=True)
    assert result["ok"] is False
    assert "newer than published" in result["errors"][0]
