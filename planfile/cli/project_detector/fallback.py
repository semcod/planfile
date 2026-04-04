"""Structure-only detection fallback."""

from __future__ import annotations

from pathlib import Path

from .base import DetectedProject
from .gates import _detect_quality_gates
from .git import _detect_git_authors
from .license import _detect_license
from .model_tier import _detect_model_tier
from .readme import _find_readme_description, _find_readme_goal
from .structure import _analyze_directory_structure


def _detect_from_structure(project_path: Path) -> DetectedProject | None:
    """Detect project info from directory structure only."""
    project = DetectedProject()

    # Use directory name as project name
    project.name = project_path.name.replace("-", " ").replace("_", " ").title()

    # Try to get description and goal from README
    project.description = _find_readme_description(project_path)
    project.goal = _find_readme_goal(project_path)

    # Infer type from structure
    if (project_path / "src").exists():
        project.project_type = "library"
    elif (project_path / "app").exists() or (project_path / "templates").exists():
        project.project_type = "web"
    elif (project_path / "api").exists():
        project.project_type = "api"
    else:
        # Check main source files
        py_files = list(project_path.glob("*.py"))
        js_files = list(project_path.glob("*.js")) + list(project_path.glob("*.ts"))

        if py_files:
            project.project_type = "cli" if len(py_files) == 1 else "library"
        elif js_files:
            project.project_type = "cli" if len(js_files) == 1 else "web"

    project.domain = "software"

    # Detect quality gates
    project.quality_gates = _detect_quality_gates(project_path, None)

    # Analyze directory structure
    project.suggested_sprints, project.has_tests = _analyze_directory_structure(project_path)
    project.has_docker = (project_path / "Dockerfile").exists()
    project.has_ci_cd = any([
        (project_path / ".github" / "workflows").exists(),
        (project_path / ".gitlab-ci.yml").exists(),
    ])

    # Detect license
    project.license = _detect_license(project_path)

    # Detect git authors
    project.authors = _detect_git_authors(project_path)

    # Detect model tier
    project.model_tier = _detect_model_tier(project_path)

    return project
