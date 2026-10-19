from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from planfile import ci_readiness as cr

REPO = Path(__file__).resolve().parents[1]
MANIFEST = {"coordination": {"workstreams": {
    "application": {"ownedPaths": ["tests/**", "planfile/**"]},
    "integration": {"ownedPaths": ["uv.lock", "pyproject.toml", "docs/**"]},
}}}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "planfile").mkdir()
    shutil.copy(REPO / "planfile/release_availability.py", tmp_path / "planfile/release_availability.py")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "planfile"\nversion = "1.2.3"\nrequires-python = ">=3.10"\n')
    (tmp_path / "uv.lock").write_text("lock-v1\n")
    metadata = {"package": "planfile", "source": {"version": "1.2.3"}, "runtime": {"version": "1.2.3", "python_requires": ">=3.10"},
                "published": {"index": "unused", "version": "1.2.3", "python_requires": ">=3.10"}}
    (tmp_path / "planfile/release-metadata.json").write_text(json.dumps(metadata))
    (tmp_path / ".governance").mkdir()
    (tmp_path / ".governance/manifest.json").write_text(json.dumps(MANIFEST))
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/internal-dependencies.json").write_text("{}")
    (tmp_path / "project").mkdir()
    (tmp_path / "project/governance-check.sh").write_text("#!/bin/sh\n")
    return tmp_path


def runner(fresh=True, governance=0, goal_missing=False):
    def run(argv, timeout):
        if argv[0] == "goal":
            if goal_missing:
                return 127, "FileNotFoundError: goal"
            report = {"fresh": fresh, "packages": [{"name": "costs", "locked": ["0.2.0"], "target": "0.2.1", "status": "current" if fresh else "outdated"}],
                      "update_command": ["uv", "lock", "--upgrade-package", "costs==0.2.1"]}
            return 0, "notice\n" + json.dumps(report)
        return governance, "line\nGOV-PASS: passed" if governance == 0 else "GOV-FAIL: failed"
    return run


def verifier(tmp_path, pyproject_digest, lock_digest):
    path = tmp_path / "check-planfile.py"
    path.write_text(f'INPUTS = {{"pyproject.toml": "{pyproject_digest}", "uv.lock": "{lock_digest}"}}\n')
    return path


def test_all_green(repo):
    pins = verifier(repo, sha((repo / "pyproject.toml").read_text()), sha("lock-v1\n"))
    report = cr.evaluate(repo, pins, runner())
    assert report.ok and not report.deadlock
    assert [r.status for r in report.results] == [cr.PASS] * 4
    assert cr.render_text(report).endswith("CI-READY")


def test_release_metadata_mismatch_is_reported_with_its_owner(repo):
    meta = json.loads((repo / "planfile/release-metadata.json").read_text())
    meta["source"]["version"] = meta["runtime"]["version"] = "1.2.2"
    (repo / "planfile/release-metadata.json").write_text(json.dumps(meta))
    report = cr.evaluate(repo, None, runner(), skip=["verifier-pins"])
    (failed,) = report.failing
    assert failed.id == "release-metadata" and "does not match" in failed.detail
    assert report.owners["release-metadata"] == ["application"] and not report.deadlock


def test_stale_dependencies_carry_the_repair_command(repo):
    report = cr.evaluate(repo, None, runner(fresh=False), skip=["verifier-pins"])
    (failed,) = report.failing
    assert failed.id == "dependency-freshness" and "costs 0.2.0 -> 0.2.1" in failed.detail
    assert failed.hint.startswith("uv lock --upgrade-package")
    assert report.owners["dependency-freshness"] == ["integration"]


def test_unavailable_goal_is_not_a_failure(repo):
    report = cr.evaluate(repo, None, runner(goal_missing=True), skip=["verifier-pins"])
    assert report.ok
    assert {r.id: r.status for r in report.results}["dependency-freshness"] == cr.UNAVAILABLE


def test_pin_drift_is_external_and_names_the_files(repo):
    pins = verifier(repo, sha((repo / "pyproject.toml").read_text()), "0" * 64)
    report = cr.evaluate(repo, pins, runner())
    (failed,) = report.failing
    assert failed.id == "verifier-pins" and "uv.lock" in failed.detail and "pyproject.toml" not in failed.detail
    assert report.owners["verifier-pins"] == ["external"]
    assert "do not edit it from this repository" in failed.hint


@pytest.mark.parametrize("content", ["INPUTS = broken(", "OTHER = {}\n"])
def test_unreadable_verifier_is_unavailable(repo, content):
    path = repo / "v.py"
    path.write_text(content)
    assert cr.check_verifier_pins(repo, path).status == cr.UNAVAILABLE


def test_missing_pinned_file_counts_as_drift(repo):
    pins = verifier(repo, sha((repo / "pyproject.toml").read_text()), sha("lock-v1\n"))
    (repo / "uv.lock").unlink()
    assert "missing" in cr.check_verifier_pins(repo, pins).detail


def test_cross_owner_failures_are_a_deadlock(repo):
    """The situation that blocked planfile: each fix belongs to a different workstream."""
    meta = json.loads((repo / "planfile/release-metadata.json").read_text())
    meta["source"]["version"] = meta["runtime"]["version"] = "1.2.2"
    (repo / "planfile/release-metadata.json").write_text(json.dumps(meta))
    report = cr.evaluate(repo, None, runner(fresh=False), skip=["verifier-pins"])
    assert len(report.failing) == 2 and report.deadlock
    text = cr.render_text(report)
    assert "DEADLOCK" in text and "application" in text and "integration" in text
    assert text.endswith("CI-NOT-READY")


def test_two_failures_with_the_same_owner_are_not_a_deadlock(repo):
    report = cr.Report(
        results=[cr.Result("a", cr.FAIL, "x", ("uv.lock",)), cr.Result("b", cr.FAIL, "y", ("pyproject.toml",))],
        owners={"a": ["integration"], "b": ["integration"]},
    )
    assert not report.deadlock


def test_governance_failure_uses_last_output_line(repo):
    result = cr.check_governance(repo, runner(governance=1))
    assert result.status == cr.FAIL and result.detail == "GOV-FAIL: failed"


def test_owners_of_handles_missing_manifest_and_external(tmp_path):
    assert cr.owners_of(tmp_path, ["uv.lock"]) == []
    assert cr.owners_of(tmp_path, ["external:verifier"]) == ["external"]


def test_cli_rejects_a_directory_that_is_not_a_repository(repo):
    assert cr.main(["--root", str(repo / "missing")]) == 2


def test_cli_exit_code_follows_the_verdict(repo, capsys):
    assert cr.main(["--root", str(repo), "--skip", "verifier-pins"], runner()) == 0
    assert capsys.readouterr().out.strip().endswith("CI-READY")
    assert cr.main(["--root", str(repo), "--skip", "verifier-pins"], runner(fresh=False)) == 1
    assert "CI-NOT-READY" in capsys.readouterr().out


def test_cli_reports_json(repo, capsys):
    assert cr.main(["--root", str(repo), "--format", "json", "--skip", "verifier-pins"], runner()) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["schema"] == "planfile.ci-readiness/v1" and data["ok"] is True and data["deadlock"] is False
    assert {c["id"] for c in data["checks"]} == {"release-metadata", "dependency-freshness", "governance"}
