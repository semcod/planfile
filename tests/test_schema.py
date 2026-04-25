"""Tests for schema validation."""

import pytest
import tempfile
import yaml
from pathlib import Path


def test_validate_planfile_valid():
    """Test validation of valid planfile.yaml."""
    from planfile.core.schema import SchemaValidator, validate_yaml_file
    
    data = {
        "schema": "1.1",
        "project": "test-project",
        "version": "1.0.0"
    }
    
    is_valid, errors = SchemaValidator.validate_planfile(data)
    assert is_valid == True
    assert len(errors) == 0


def test_validate_planfile_missing_required_field():
    """Test validation fails with missing required field."""
    from planfile.core.schema import SchemaValidator
    
    data = {
        "version": "1.0.0"
    }
    
    is_valid, errors = SchemaValidator.validate_planfile(data)
    assert is_valid == False
    assert "Missing required field: schema" in errors
    assert "Missing required field: project" in errors


def test_validate_planfile_schema_version_mismatch():
    """Test validation fails with schema version mismatch."""
    from planfile.core.schema import SchemaValidator
    
    data = {
        "schema": "1.0",
        "project": "test-project"
    }
    
    is_valid, errors = SchemaValidator.validate_planfile(data)
    assert is_valid == False
    assert "Schema version mismatch" in errors[0]


def test_validate_planfile_wrong_type():
    """Test validation fails with wrong field type."""
    from planfile.core.schema import SchemaValidator
    
    data = {
        "schema": "1.1",
        "project": "test-project",
        "sources": "not-a-list"  # Should be list
    }
    
    is_valid, errors = SchemaValidator.validate_planfile(data)
    assert is_valid == False
    assert any("sources" in error for error in errors)


def test_validate_sprint_valid():
    """Test validation of valid sprint YAML."""
    from planfile.core.schema import SchemaValidator
    
    data = {
        "sprint": {
            "id": "sprint-001",
            "name": "Sprint 1"
        }
    }
    
    is_valid, errors = SchemaValidator.validate_sprint(data)
    assert is_valid == True
    assert len(errors) == 0


def test_validate_sprint_missing_required_field():
    """Test validation fails with missing sprint field."""
    from planfile.core.schema import SchemaValidator
    
    data = {
        "id": "sprint-001"
    }
    
    is_valid, errors = SchemaValidator.validate_sprint(data)
    assert is_valid == False
    assert "Missing required field: sprint" in errors


def test_validate_sprint_missing_sprint_id():
    """Test validation fails with missing sprint.id."""
    from planfile.core.schema import SchemaValidator
    
    data = {
        "sprint": {
            "name": "Sprint 1"
        }
    }
    
    is_valid, errors = SchemaValidator.validate_sprint(data)
    assert is_valid == False
    assert "Missing required field: sprint.id" in errors


def test_validate_yaml_file_planfile():
    """Test validate_yaml_file with planfile type."""
    from planfile.core.schema import validate_yaml_file
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_file = tmpdir_path / "planfile.yaml"
        
        data = {
            "schema": "1.1",
            "project": "test-project"
        }
        
        with open(yaml_file, 'w') as f:
            yaml.dump(data, f)
        
        is_valid, errors = validate_yaml_file(yaml_file, "planfile")
        assert is_valid == True
        assert len(errors) == 0


def test_validate_yaml_file_invalid_yaml():
    """Test validate_yaml_file with invalid YAML."""
    from planfile.core.schema import validate_yaml_file
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        yaml_file = tmpdir_path / "invalid.yaml"
        
        with open(yaml_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        is_valid, errors = validate_yaml_file(yaml_file, "planfile")
        assert is_valid == False
        assert "Invalid YAML" in errors[0]


def test_validate_yaml_file_not_found():
    """Test validate_yaml_file with non-existent file."""
    from planfile.core.schema import validate_yaml_file
    
    is_valid, errors = validate_yaml_file(Path("/nonexistent/file.yaml"), "planfile")
    assert is_valid == False
    assert "File not found" in errors[0]


def test_get_current_schema_version():
    """Test getting current schema version."""
    from planfile.core.schema import SchemaValidator
    
    version = SchemaValidator.get_current_schema_version()
    assert version == "1.1"
