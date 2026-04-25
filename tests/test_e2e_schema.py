"""E2E tests for schema validation."""

import pytest
import tempfile
import yaml
from pathlib import Path
import subprocess
import sys


def test_e2e_validate_schema_valid_planfile():
    """E2E test: validate valid planfile.yaml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create valid planfile.yaml
        data = {
            "schema": "1.1",
            "project": "test-project",
            "version": "1.0.0"
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile validate schema
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "validate", "schema", str(planfile_yaml)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Schema validation passed" in result.stdout


def test_e2e_validate_schema_missing_required_field():
    """E2E test: validate planfile.yaml with missing required field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml without schema field
        data = {
            "project": "test-project",
            "version": "1.0.0"
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile validate schema
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "validate", "schema", str(planfile_yaml)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "Schema validation failed" in result.stdout
        assert "Missing required field" in result.stdout


def test_e2e_validate_schema_version_mismatch():
    """E2E test: validate planfile.yaml with wrong schema version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create planfile.yaml with wrong schema version
        data = {
            "schema": "1.0",
            "project": "test-project"
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile validate schema
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "validate", "schema", str(planfile_yaml)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "Schema validation failed" in result.stdout
        assert "Schema version mismatch" in result.stdout


def test_e2e_validate_schema_invalid_yaml():
    """E2E test: validate invalid YAML file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_file = tmpdir_path / "invalid.yaml"
        
        # Create invalid YAML
        with open(yaml_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        # Run planfile validate schema
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "validate", "schema", str(yaml_file)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 1
        assert "Schema validation failed" in result.stdout


def test_e2e_validate_schema_sprint_yaml():
    """E2E test: validate sprint YAML file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        sprint_yaml = tmpdir_path / "sprint.yaml"
        
        # Create valid sprint YAML
        data = {
            "sprint": {
                "id": "sprint-001",
                "name": "Sprint 1"
            }
        }
        
        with open(sprint_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile validate schema
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "validate", "schema", str(sprint_yaml), "--file-type", "sprint"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Schema validation passed" in result.stdout


def test_e2e_validate_schema_verbose():
    """E2E test: validate schema with verbose output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        planfile_yaml = tmpdir_path / "planfile.yaml"
        
        # Create valid planfile.yaml
        data = {
            "schema": "1.1",
            "project": "test-project"
        }
        
        with open(planfile_yaml, 'w') as f:
            yaml.dump(data, f)
        
        # Run planfile validate schema with verbose
        result = subprocess.run(
            [sys.executable, "-m", "planfile.cli", "validate", "schema", str(planfile_yaml), "--verbose"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Schema validation passed" in result.stdout
        assert "Current schema version" in result.stdout
        assert "File schema version" in result.stdout
