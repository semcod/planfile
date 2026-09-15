"""Schema validation and versioning for Planfile YAML documents."""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from planfile.core.configuration import STORE_SETTINGS

# Schema versions
CURRENT_SCHEMA_VERSION = "1.1"
PLANFILE_SCHEMA_VERSION = "1.1"
SPRINT_SCHEMA_VERSION = "1.0"
CONFIG_SCHEMA_VERSION = "1.0"

_CONFIG_LEAF_SETTINGS = {
    "project": "store.project",
    "prefix": "store.prefix",
}
_CONFIG_SECTION_SETTINGS = {
    "archive": {
        "enabled": "store.archive.enabled",
        "max_current_tickets": "store.archive.max_current_tickets",
        "max_current_bytes": "store.archive.max_current_bytes",
        "retain_terminal_tickets": "store.archive.retain_terminal_tickets",
        "retain_terminal_days": "store.archive.retain_terminal_days",
        "terminal_statuses": "store.archive.terminal_statuses",
    },
    "storage": {
        "backend": "store.storage.backend",
        "shard_size": "store.storage.shard_size",
        "custom_shards": "store.storage.custom_shards",
        "index": "store.storage.index",
    },
}


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
    def validate_config(cls, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate the repository-local ``.planfile/config.yaml`` contract."""
        errors: list[str] = []
        if not isinstance(data, dict):
            return False, ["Configuration document must be a mapping"]

        required = {"project", "prefix", "next_id"}
        for field in sorted(required - set(data)):
            errors.append(f"Missing required config field: {field}")

        allowed = set(_CONFIG_LEAF_SETTINGS) | {"next_id", *_CONFIG_SECTION_SETTINGS}
        for field in sorted(set(data) - allowed):
            errors.append(f"Unknown config field: {field}")

        for field, setting_path in _CONFIG_LEAF_SETTINGS.items():
            if field not in data:
                continue
            validator = STORE_SETTINGS[setting_path].validator
            try:
                validator(data[field])
            except (TypeError, ValueError) as error:
                errors.append(f"Invalid config field {field}: {error}")

        if "next_id" in data and (
            isinstance(data["next_id"], bool)
            or not isinstance(data["next_id"], int)
            or data["next_id"] < 1
        ):
            errors.append("Invalid config field next_id: positive integer required")

        for section, settings in _CONFIG_SECTION_SETTINGS.items():
            if section not in data:
                continue
            value = data[section]
            if not isinstance(value, dict):
                errors.append(f"Config section {section} must be a mapping")
                continue
            for field in sorted(set(value) - set(settings)):
                errors.append(f"Unknown config field: {section}.{field}")
            for field, setting_path in settings.items():
                if field not in value:
                    continue
                validator = STORE_SETTINGS[setting_path].validator
                try:
                    validator(value[field])
                except (TypeError, ValueError) as error:
                    errors.append(f"Invalid config field {section}.{field}: {error}")

        return len(errors) == 0, errors
    
    @classmethod
    def get_current_schema_version(cls) -> str:
        """Get the current schema version."""
        return CURRENT_SCHEMA_VERSION


def detect_document_type(data: Dict[str, Any]) -> str:
    """Infer the schema contract represented by a loaded YAML document."""
    if not isinstance(data, dict):
        return "unknown"
    if {"project", "prefix", "next_id"}.issubset(data) or any(
        key in data for key in ("archive", "storage")
    ):
        return "config"
    if "sprint" in data and isinstance(data.get("sprint"), dict):
        return "sprint"
    if "schema" in data and "project" in data:
        return "planfile"
    if "name" in data and ("sprints" in data or "quality_gates" in data):
        return "strategy"
    return "unknown"


def detect_file_type(file_path: Path) -> str:
    """Infer a YAML document type without walking outside ``file_path``."""
    if file_path.name == "config.yaml" and file_path.parent.name == ".planfile":
        return "config"
    try:
        with open(file_path, encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError):
        return "planfile"
    detected = detect_document_type(data)
    return "planfile" if detected == "unknown" else detected


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

    if not isinstance(data, dict):
        return False, ["YAML document must be a mapping"]
    
    if file_type == "auto":
        file_type = detect_document_type(data)

    if file_type == "planfile":
        return SchemaValidator.validate_planfile(data)
    elif file_type == "sprint":
        return SchemaValidator.validate_sprint(data)
    elif file_type == "config":
        return SchemaValidator.validate_config(data)
    elif file_type == "strategy":
        from planfile.core.models.strategy import Strategy

        try:
            Strategy(**data)
        except Exception as error:
            return False, [str(error)]
        return True, []
    else:
        return False, [f"Unknown file type: {file_type}"]
