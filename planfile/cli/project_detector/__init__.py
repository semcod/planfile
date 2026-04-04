"""Project auto-detection module for planfile init.

Detects project information from:
- pyproject.toml (Python projects)
- package.json (Node.js projects)
- README.md (project description and goal)
- Directory structure (project type inference)
- Project files (quality gates, CI/CD, tests)
- Git configuration (authors)
- Environment/API configuration (model tier)
"""

from __future__ import annotations

from .base import DetectedProject, DetectedQualityGate
from .main import detect_project, get_detected_values

__all__ = [
    "DetectedProject",
    "DetectedQualityGate",
    "detect_project",
    "get_detected_values",
]
