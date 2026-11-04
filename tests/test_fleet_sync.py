"""Tests for fleet synchronization and 6-hour systemd schedule generation."""

from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from planfile.cli.groups.sync import register_sync_commands
from planfile.cli.groups.sync.fleet import (
    discover_fleet_repositories,
    generate_service_content,
    generate_timer_content,
    sync_fleet,
)
from planfile.sync.operations import is_incident_noise


@pytest.fixture()
def sync_cli():
    app = typer.Typer()
    register_sync_commands(app)
    return app


def test_is_incident_noise_detects_crash_and_degradation():
    assert is_incident_noise({"id": "1", "name": "[computer-use:autocontrol-browser] Auto-detected degradation: browser_navigation_stalled"})
    assert is_incident_noise({"id": "2", "name": "[autocontrol-browser] Runtime crash: cdp session died"})
    assert is_incident_noise({"id": "3", "name": "Runtime crash: segmentation fault"})
    assert is_incident_noise({"id": "4", "name": "Auto-detected degradation: latency spike"})
    assert is_incident_noise({"id": "5", "name": "Fix navigation in cdp_form", "labels": ["incident", "browser"]})
    assert is_incident_noise({"id": "6", "name": "Memory issue", "labels": ["incident-report"]})
    assert not is_incident_noise({"id": "7", "name": "Implement user authentication", "labels": ["feature", "auth"]})
    assert not is_incident_noise({"id": "8", "name": "Refactor database models", "labels": ["task"]})


def test_discover_fleet_repositories(tmp_path):
    # Repo 1: valid with github integration
    repo1 = tmp_path / "org" / "proj1"
    planfile1 = repo1 / ".planfile"
    planfile1.mkdir(parents=True)
    (planfile1 / "github.planfile.yaml").write_text("integrations:\n  github:\n    repo: org/proj1\n")

    # Repo 2: planfile present but no github
    repo2 = tmp_path / "org" / "proj2"
    planfile2 = repo2 / ".planfile"
    planfile2.mkdir(parents=True)

    # Repo 3: no planfile
    repo3 = tmp_path / "org" / "proj3"
    repo3.mkdir(parents=True)

    discovered = discover_fleet_repositories(tmp_path, max_depth=2)
    assert len(discovered) == 1
    path, gh_repo = discovered[0]
    assert path == repo1
    assert gh_repo == "org/proj1"


def test_generate_service_and_timer_content(tmp_path):
    service = generate_service_content(root=tmp_path, planfile_bin="/usr/local/bin/planfile")
    assert "/usr/local/bin/planfile sync fleet" in service
    assert str(tmp_path.resolve()) in service

    timer = generate_timer_content(interval_hours=6)
    assert "OnUnitActiveSec=6h" in timer
    assert "Unit=planfile-fleet-sync.service" in timer


def test_sync_fleet_runs_bounded_integration(tmp_path):
    repo1 = tmp_path / "group" / "repo1"
    planfile1 = repo1 / ".planfile"
    planfile1.mkdir(parents=True)
    (planfile1 / "github.planfile.yaml").write_text("integrations:\n  github:\n    repo: group/repo1\n")

    with patch("planfile.cli.groups.sync.fleet.sync_integration") as mock_sync:
        stats = sync_fleet(tmp_path, max_depth=2, dry_run=True, exclude_incident_noise=True)
        assert stats["scanned"] == 1
        assert stats["synced"] == 1
        assert stats["failed"] == 0
        mock_sync.assert_called_once()
        args, kwargs = mock_sync.call_args
        assert args[0] == "github"
        assert args[1] == str(repo1)
        assert kwargs["direction"] == "from"
        assert kwargs["dry_run"] is True
        assert kwargs["exclude_incident_noise"] is True


def test_fleet_cli_dry_run(sync_cli, tmp_path):
    runner = CliRunner()
    result = runner.invoke(sync_cli, ["sync", "fleet", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "No GitHub-integrated repositories found" in result.output
