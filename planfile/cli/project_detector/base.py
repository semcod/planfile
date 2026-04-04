"""Project auto-detection - base types and dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DetectedQualityGate:
    """Detected quality gate from project files."""
    name: str
    description: str
    criteria: list[str]
    required: bool = True


@dataclass
class DetectedProject:
    """Container for detected project information."""
    name: str | None = None
    description: str | None = None
    goal: str | None = None
    version: str | None = None
    project_type: str | None = None  # api, web, cli, library
    domain: str | None = None
    authors: list[str] = field(default_factory=list)
    license: str | None = None
    source_dir: str | None = None
    quality_gates: list[DetectedQualityGate] = field(default_factory=list)
    suggested_sprints: list[dict] = field(default_factory=list)
    model_tier: str | None = None
    has_ci_cd: bool = False
    has_tests: bool = False
    has_docker: bool = False
