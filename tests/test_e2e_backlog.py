"""E2E tests for backlog commands."""

import pytest
import tempfile
import yaml
from pathlib import Path
import subprocess
import sys


def test_e2e_backlog_list_empty():
    """E2E test: list backlog with no items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml with no backlog
        data = {
            "name": "test",
            "project_name": "test"
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile backlog list
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "backlog", "list"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "No backlog items found" in result.stdout


def test_e2e_backlog_list_with_items():
    """E2E test: list backlog with items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml with backlog items
        data = {
            "name": "test",
            "project_name": "test",
            "backlog": [
                {
                    "id": "ticket-001",
                    "name": "Test ticket",
                    "files": ["src/main.py"],
                    "priority": "medium"
                }
            ]
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile backlog list
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "backlog", "list"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "ticket-001" in result.stdout
        assert "Test ticket" in result.stdout


def test_e2e_backlog_list_with_files_filter():
    """E2E test: list backlog with files filter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml with backlog items
        data = {
            "name": "test",
            "project_name": "test",
            "backlog": [
                {
                    "id": "ticket-001",
                    "name": "Archive ticket",
                    "files": ["_archive/test.py"],
                    "priority": "medium"
                },
                {
                    "id": "ticket-002",
                    "name": "Source ticket",
                    "files": ["src/main.py"],
                    "priority": "high"
                }
            ]
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile backlog list with filter
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "backlog", "list", "--files", "_archive*"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "ticket-001" in result.stdout
        assert "ticket-002" not in result.stdout


def test_e2e_backlog_delete_dry_run():
    """E2E test: delete backlog with dry run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml with backlog items
        data = {
            "name": "test",
            "project_name": "test",
            "backlog": [
                {
                    "id": "ticket-001",
                    "name": "Archive ticket",
                    "files": ["_archive/test.py"],
                    "priority": "medium"
                }
            ]
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile backlog delete with dry run
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "backlog", "delete", "--files", "_archive*", "--dry-run", "--force"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "ticket-001" in result.stdout
        assert "--dry-run" in result.stdout
        
        # Verify file wasn't modified
        with open(planfile_yaml) as f:
            data_after = yaml.safe_load(f)
            assert len(data_after['backlog']) == 1


def test_e2e_backlog_delete_force():
    """E2E test: delete backlog with force."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml with backlog items
        data = {
            "name": "test",
            "project_name": "test",
            "backlog": [
                {
                    "id": "ticket-001",
                    "name": "Archive ticket",
                    "files": ["_archive/test.py"],
                    "priority": "medium"
                }
            ]
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile backlog delete with force
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "backlog", "delete", "--files", "_archive*", "--force"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Deleted 1 item(s)" in result.stdout
        
        # Verify file was modified
        with open(planfile_yaml) as f:
            data_after = yaml.safe_load(f)
            assert len(data_after['backlog']) == 0


def test_e2e_backlog_delete_targets():
    """E2E test: delete backlog with targets section."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml with targets
        data = {
            "name": "test",
            "project_name": "test",
            "targets": {
                "final": {
                    "backend_lines": 36000,
                    "files": ["_archive/test.py"],
                    "rule_id": "smart-return-type"
                }
            }
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile backlog delete with targets
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "backlog", "delete", "--files", "_archive*", "--targets", "--force"],
            cwd=tmpdir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "targets.final" in result.stdout
        
        # Verify targets were cleaned
        with open(planfile_yaml) as f:
            data_after = yaml.safe_load(f)
            assert 'files' not in data_after['targets']['final']
            assert 'rule_id' not in data_after['targets']['final']
