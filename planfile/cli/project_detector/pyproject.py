"""pyproject.toml detection for Python projects."""

from __future__ import annotations

from pathlib import Path

from .base import DetectedProject
from .gates import _detect_quality_gates
from .git import _detect_git_authors
from .license import _detect_license
from .model_tier import _detect_model_tier
from .readme import _find_readme_description, _find_readme_goal
from .structure import _analyze_directory_structure
from .inference import _infer_python_project_type, _infer_domain


def _detect_from_pyproject(project_path: Path) -> DetectedProject | None:
    """Detect project info from pyproject.toml."""
    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return None

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return None

    project = DetectedProject()

    # Try [project] section first (PEP 621)
    if "project" in data:
        proj = data["project"]
        project.name = proj.get("name")
        project.description = proj.get("description")
        project.version = proj.get("version")
        project.license = proj.get("license", {}).get("text") if isinstance(proj.get("license"), dict) else proj.get("license")

        # Authors
        if "authors" in proj:
            for author in proj["authors"]:
                if isinstance(author, dict):
                    name = author.get("name", "")
                    email = author.get("email", "")
                    if name and email:
                        project.authors.append(f"{name} <{email}>")
                    elif name:
                        project.authors.append(name)

    # Fallback to [tool.poetry]
    if not project.name and "tool" in data and "poetry" in data["tool"]:
        poetry = data["tool"]["poetry"]
        project.name = poetry.get("name")
        project.description = poetry.get("description")
        project.version = poetry.get("version")
        if poetry.get("authors"):
            project.authors.extend(poetry["authors"])

    # Detect project type from dependencies and scripts
    deps = []
    if "project" in data and "dependencies" in data["project"]:
        deps = data["project"]["dependencies"]
    elif "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
        deps = list(data["tool"]["poetry"]["dependencies"].keys())

    project.project_type = _infer_python_project_type(deps, data, project_path)

    # Detect domain from keywords/classifiers
    if "project" in data:
        keywords = data["project"].get("keywords", [])
        classifiers = data["project"].get("classifiers", [])
        project.domain = _infer_domain(keywords, classifiers, project.description or "")

    # Detect quality gates
    project.quality_gates = _detect_quality_gates(project_path, data)

    # If no description from pyproject, try README
    if not project.description:
        project.description = _find_readme_description(project_path)

    # Get goal from README
    project.goal = _find_readme_goal(project_path)

    # Analyze directory structure for sprint suggestions
    project.suggested_sprints, project.has_tests = _analyze_directory_structure(project_path)
    project.has_docker = (project_path / "Dockerfile").exists()
    project.has_ci_cd = any([
        (project_path / ".github" / "workflows").exists(),
        (project_path / ".gitlab-ci.yml").exists(),
    ])

    # Detect license if not in pyproject
    if not project.license:
        project.license = _detect_license(project_path)

    # Detect git authors if none found
    if not project.authors:
        project.authors = _detect_git_authors(project_path)

    # Detect model tier
    project.model_tier = _detect_model_tier(project_path)

    return project if project.name else None
