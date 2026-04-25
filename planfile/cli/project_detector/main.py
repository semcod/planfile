"""Main project detection entry points."""

from __future__ import annotations

from pathlib import Path

from .base import DetectedProject
from .fallback import _detect_from_structure
from .package import _detect_from_package_json
from .pyproject import _detect_from_pyproject


def detect_project(project_path: Path | None = None) -> DetectedProject:
    """
    Auto-detect project information from various sources.
    
    Args:
        project_path: Path to project directory (default: current directory)
    
    Returns:
        DetectedProject with discovered information
    """
    if project_path is None:
        project_path = Path.cwd()
    else:
        project_path = Path(project_path)

    # Try pyproject.toml first (Python)
    project = _detect_from_pyproject(project_path)
    if project:
        return project

    # Try package.json (Node.js)
    project = _detect_from_package_json(project_path)
    if project:
        return project

    # Fallback to structure detection
    return _detect_from_structure(project_path)


def _quality_gates_to_dict(gates: list) -> list[dict]:
    """Convert quality gates to dict format."""
    return [
        {
            "name": gate.name,
            "description": gate.description,
            "criteria": gate.criteria,
            "required": gate.required,
        }
        for gate in gates
    ]


def _determine_source(detected: DetectedProject) -> str:
    """Determine the detection source based on project files."""
    if not detected.name:
        return "structure"
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return "pyproject.toml"
    if (cwd / "package.json").exists():
        return "package.json"
    return "README"


def _build_detected_dict(detected: DetectedProject) -> dict:
    """Build a dictionary from detected project values."""
    quality_gates = _quality_gates_to_dict(detected.quality_gates)
    source = _determine_source(detected)

    return {
        "name": detected.name or "",
        "description": detected.description or "",
        "goal": detected.goal or "",
        "version": detected.version or "1.0.0",
        "project_type": detected.project_type or "api",
        "domain": detected.domain or "software",
        "license": detected.license or "",
        "authors": detected.authors,
        "has_ci_cd": detected.has_ci_cd,
        "has_tests": detected.has_tests,
        "has_docker": detected.has_docker,
        "quality_gates": quality_gates,
        "suggested_sprints": detected.suggested_sprints,
        "model_tier": detected.model_tier or "cheap",
        "has_detection": bool(detected.name),
        "source": source,
    }


def get_detected_values() -> dict:
    """
    Get detected project values as a dictionary for use in CLI.

    Returns:
        Dict with detected values or empty strings if not detected
    """
    detected = detect_project()
    return _build_detected_dict(detected)
