"""Schema validation and versioning for planfile YAML files."""

from typing import Any, Dict, List
import yaml
from pathlib import Path


# Schema versions
CURRENT_SCHEMA_VERSION = "1.1"
PLANFILE_SCHEMA_VERSION = "1.1"
SPRINT_SCHEMA_VERSION = "1.0"


class SchemaValidator:
    """Validate planfile YAML files against schema definitions."""
    
    # Schema definitions
    SCHEMAS = {
        "planfile": {
            "version": PLANFILE_SCHEMA_VERSION,
            "required_fields": ["schema", "project"],
            "optional_fields": ["version", "generated", "generator", "sources", "stats", "tasks", "sprints", "targets", "backlog"],
            "structure": {
                "schema": str,
                "project": str,
                "version": str,
                "generated": str,
                "generator": str,
                "sources": list,
                "stats": dict,
                "tasks": list,
                "sprints": list,
                "targets": dict,
                "backlog": list,
            }
        },
        "sprint": {
            "version": SPRINT_SCHEMA_VERSION,
            "required_fields": ["sprint"],
            "optional_fields": [],
            "structure": {
                "sprint": dict,
            }
        }
    }
    
    @classmethod
    def validate_planfile(cls, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate planfile.yaml structure."""
        schema = cls.SCHEMAS["planfile"]
        errors = []
        
        # Check required fields
        for field in schema["required_fields"]:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Check schema version
        if "schema" in data:
            schema_version = data["schema"]
            if schema_version != schema["version"]:
                errors.append(f"Schema version mismatch: expected {schema['version']}, got {schema_version}")
        
        # Validate structure types
        for field, expected_type in schema["structure"].items():
            if field in data and not isinstance(data[field], expected_type):
                errors.append(f"Field '{field}' should be {expected_type.__name__}, got {type(data[field]).__name__}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_sprint(cls, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate sprint YAML structure."""
        schema = cls.SCHEMAS["sprint"]
        errors = []
        
        # Check required fields
        for field in schema["required_fields"]:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Validate sprint structure
        if "sprint" in data and isinstance(data["sprint"], dict):
            sprint_data = data["sprint"]
            if "id" not in sprint_data:
                errors.append("Missing required field: sprint.id")
            if "name" not in sprint_data:
                errors.append("Missing required field: sprint.name")
        
        return len(errors) == 0, errors
    
    @classmethod
    def get_current_schema_version(cls) -> str:
        """Get the current schema version."""
        return CURRENT_SCHEMA_VERSION


def detect_document_type(data: Dict[str, Any]) -> str:
    """Infer which schema a loaded YAML document is meant to satisfy.

    A ticket-store `planfile.yaml` and a `Strategy` file are different documents
    that happen to share an extension. Guessing "planfile" for both makes every
    generated strategy fail validation for missing ticket-store keys.
    """
    if not isinstance(data, dict):
        return "planfile"
    if "sprint" in data and isinstance(data.get("sprint"), dict):
        return "sprint"
    if "schema" in data and "project" in data:
        return "planfile"
    # A Strategy always names itself and carries sprints and/or quality gates.
    if "name" in data and ("sprints" in data or "quality_gates" in data):
        return "strategy"
    return "planfile"


def detect_file_type(file_path: Path) -> str:
    """Infer the document type of a YAML file on disk (safe on unreadable files)."""
    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return "planfile"
    return detect_document_type(data)


def validate_yaml_file(file_path: Path, file_type: str = "planfile") -> tuple[bool, List[str]]:
    """Validate a YAML file against its schema."""
    if not file_path.exists():
        return False, [f"File not found: {file_path}"]
    
    with open(file_path) as f:
        try:
            from planfile.core.fastio import FastLoader

            data = yaml.load(f, Loader=FastLoader)
        except yaml.YAMLError as e:
            return False, [f"Invalid YAML: {e}"]
    
    if file_type == "auto":
        file_type = detect_document_type(data)

    if file_type == "planfile":
        return SchemaValidator.validate_planfile(data)
    elif file_type == "sprint":
        return SchemaValidator.validate_sprint(data)
    elif file_type == "strategy":
        from planfile.core.models.strategy import Strategy

        try:
            Strategy(**data)
        except Exception as e:  # pydantic ValidationError and friends
            return False, [str(e)]
        return True, []
    else:
        return False, [f"Unknown file type: {file_type}"]
