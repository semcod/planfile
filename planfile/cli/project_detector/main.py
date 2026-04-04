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


def get_detected_values() -> dict:
    """
    Get detected project values as a dictionary for use in CLI.
    
    Returns:
        Dict with detected values or empty strings if not detected
    """
    detected = detect_project()

    # Convert quality gates to dict format
    quality_gates = []
    for gate in detected.quality_gates:
        quality_gates.append({
            "name": gate.name,
            "description": gate.description,
            "criteria": gate.criteria,
            "required": gate.required,
        })

    # Determine source
    source = "structure"
    if detected.name:
        if (Path.cwd() / "pyproject.toml").exists():
            source = "pyproject.toml"
        elif (Path.cwd() / "package.json").exists():
            source = "package.json"
        elif detected.description and not detected.name:
            source = "README"

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
