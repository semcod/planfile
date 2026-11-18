from __future__ import annotations

import importlib.util
import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 uses the locked tomli dependency.
    import tomli as tomllib

SPEC = importlib.util.spec_from_file_location("release_availability", Path(__file__).parents[1] / "planfile/release_availability.py")
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


def test_release_metadata_matches_published_offline_snapshot():
    root = Path(__file__).parents[1]
    result = CHECKER.check(root, offline=True)
    assert result["ok"] is True, result["errors"]
    # The release number belongs to pyproject.toml; a test that repeats it breaks on every bump.
    declared = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    assert result["source_version"] == declared


def test_newer_source_version_is_rejected(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "planfile"\nversion = "0.1.127"\nrequires-python = ">=3.10"\n')
    (tmp_path / "planfile").mkdir()
    metadata = {"package": "planfile", "source": {"version": "0.1.127"}, "runtime": {"version": "0.1.127", "python_requires": ">=3.10"}, "published": {"index": "unused", "version": "0.1.126", "python_requires": ">=3.10"}}
    (tmp_path / "planfile/release-metadata.json").write_text(json.dumps(metadata))
    result = CHECKER.check(tmp_path, offline=True)
    assert result["ok"] is False
    assert "newer than published" in result["errors"][0]


def test_stale_runtime_init_constant_is_detected(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "planfile"\nversion = "0.1.127"\nrequires-python = ">=3.10"\n')
    (tmp_path / "planfile").mkdir()
    (tmp_path / "planfile/__init__.py").write_text('__version__ = "0.1.126"\n')
    metadata = {
        "package": "planfile",
        "source": {"version": "0.1.127"},
        "runtime": {"version": "0.1.127", "python_requires": ">=3.10"},
        "published": {"index": "unused", "version": "0.1.127", "python_requires": ">=3.10"},
    }
    (tmp_path / "planfile/release-metadata.json").write_text(json.dumps(metadata))
    result = CHECKER.check(tmp_path, offline=True)
    assert result["ok"] is False
    assert result["runtime_version_constant"] == "0.1.126"
    assert any("does not match pyproject" in err for err in result["errors"])


def test_stale_version_identity_constant_is_detected(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "planfile"\nversion = "0.1.127"\nrequires-python = ">=3.10"\n')
    (tmp_path / "planfile").mkdir()
    (tmp_path / "planfile/__init__.py").write_text(
        'from planfile.version_identity import RUNTIME_VERSION_CONSTANT, resolve_runtime_version\n'
        '__version__ = resolve_runtime_version(RUNTIME_VERSION_CONSTANT, package_file=__file__)\n'
    )
    (tmp_path / "planfile/version_identity.py").write_text('RUNTIME_VERSION_CONSTANT = "0.1.126"\n')
    metadata = {
        "package": "planfile",
        "source": {"version": "0.1.127"},
        "runtime": {"version": "0.1.127", "python_requires": ">=3.10"},
        "published": {"index": "unused", "version": "0.1.127", "python_requires": ">=3.10"},
    }
    (tmp_path / "planfile/release-metadata.json").write_text(json.dumps(metadata))
    result = CHECKER.check(tmp_path, offline=True)
    assert result["ok"] is False
    assert result["runtime_version_constant"] == "0.1.126"
    assert any("does not match pyproject" in err for err in result["errors"])


def test_distribution_qualification_reports_procache_blocker_and_clean_env(tmp_path):
    root = Path(__file__).parents[1]
    repo_result = CHECKER.check(root, offline=True)
    qual = repo_result["distribution_qualification"]
    assert qual["minimal_sdk_import_is_full_qualification"] is False
    assert qual["qualified_full_offline_install"] is False
    assert qual["status"] == "blocked"
    assert qual["blockers"]
    assert any("procache" in b["dependency"] and b["tracking_issues"] == ["#303", "#329"] for b in qual["blockers"])

    # Clean dependency graph still requires an explicit clean offline install proof.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "planfile"\nversion = "0.1.127"\nrequires-python = ">=3.10"\ndependencies = ["pydantic>=2.0"]\n'
    )
    unverified = CHECKER.qualify_distribution_install(tmp_path)
    assert unverified["status"] == "unverified"
    assert unverified["qualified_full_offline_install"] is False
    assert unverified["minimal_sdk_import_is_full_qualification"] is False

    qualified = CHECKER.qualify_distribution_install(
        tmp_path,
        clean_env_result={
            "ok": True,
            "network_disabled": True,
            "all_public_dependencies_imported": True,
        },
    )
    assert qualified["status"] == "qualified"
    assert qualified["qualified_full_offline_install"] is True
    assert qualified["minimal_sdk_import_is_full_qualification"] is False
