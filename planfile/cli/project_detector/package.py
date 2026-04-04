"""package.json detection for Node.js projects."""

from __future__ import annotations

import json
from pathlib import Path

from .base import DetectedProject
from .gates import _detect_quality_gates
from .git import _detect_git_authors
from .license import _detect_license
from .model_tier import _detect_model_tier
from .readme import _find_readme_description, _find_readme_goal
from .structure import _analyze_directory_structure
from .inference import _infer_node_project_type, _infer_domain


def _detect_from_package_json(project_path: Path) -> DetectedProject | None:
    """Detect project info from package.json (Node.js)."""
    package_path = project_path / "package.json"
    if not package_path.exists():
        return None

    try:
        with open(package_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    project = DetectedProject()
    project.name = data.get("name")
    project.description = data.get("description")
    project.version = data.get("version")

    # Detect project type from dependencies
    deps = list(data.get("dependencies", {}).keys())
    dev_deps = list(data.get("devDependencies", {}).keys())
    all_deps = deps + dev_deps

    project.project_type = _infer_node_project_type(all_deps, data)

    # Detect domain from keywords
    keywords = data.get("keywords", [])
    project.domain = _infer_domain(keywords, [], project.description or "")

    # Detect quality gates
    project.quality_gates = _detect_quality_gates(project_path, None)

    # If no description, try README
    if not project.description:
        project.description = _find_readme_description(project_path)

    # Get goal from README
    project.goal = _find_readme_goal(project_path)

    # Analyze directory structure
    project.suggested_sprints, project.has_tests = _analyze_directory_structure(project_path)
    project.has_docker = (project_path / "Dockerfile").exists()
    project.has_ci_cd = any([
        (project_path / ".github" / "workflows").exists(),
        (project_path / ".gitlab-ci.yml").exists(),
    ])

    # Detect license
    project.license = data.get("license") or _detect_license(project_path)

    # Detect git authors
    project.authors = _detect_git_authors(project_path)

    # Detect model tier
    project.model_tier = _detect_model_tier(project_path)

    return project if project.name else None
