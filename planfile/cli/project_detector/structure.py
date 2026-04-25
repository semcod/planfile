"""Directory structure analysis for sprint suggestions."""

from __future__ import annotations

from pathlib import Path


def _has_tests(project_path: Path) -> bool:
    """Check if project has test directories."""
    return (project_path / "tests").exists() or (project_path / "test").exists()


def _find_src_dirs(project_path: Path) -> list[str]:
    """Find source directories in project."""
    if (project_path / "src").exists():
        src_path = project_path / "src"
        return [d.name for d in src_path.iterdir() if d.is_dir() and not d.name.startswith('.')]

    pkg_name = project_path.name.replace('-', '_').replace(' ', '_')
    if (project_path / pkg_name).exists():
        return [pkg_name]

    # Find main Python/JS directories
    py_dirs = [d.name for d in project_path.iterdir()
               if d.is_dir() and d.name not in ("venv", ".venv")
               and not d.name.startswith('.') and not d.name.startswith('__')]
    return py_dirs[:3] if py_dirs else []


def _suggest_sprints(project_path: Path, src_dirs: list[str], has_tests: bool) -> list[dict]:
    """Generate sprint suggestions based on project structure."""
    sprints = []

    if src_dirs:
        components = ", ".join(src_dirs[:3])
        sprints.append({
            "name": "Core Implementation",
            "objectives": [f"Implement {components} modules", "Set up project structure"]
        })

    if has_tests:
        sprints.append({
            "name": "Testing & Quality",
            "objectives": ["Write comprehensive tests", "Set up CI/CD pipeline"]
        })

    if (project_path / "docs").exists() or (project_path / "README.md").exists():
        sprints.append({
            "name": "Documentation",
            "objectives": ["Complete API documentation", "Write usage examples"]
        })

    if (project_path / "Dockerfile").exists():
        sprints.append({
            "name": "Deployment",
            "objectives": ["Containerize application", "Set up deployment pipeline"]
        })

    return sprints


def _analyze_directory_structure(project_path: Path) -> tuple[list[dict], bool]:
    """
    Analyze directory structure and suggest sprint structure.
    Returns: (suggested_sprints, has_tests)
    """
    has_tests = _has_tests(project_path)
    src_dirs = _find_src_dirs(project_path)
    sprints = _suggest_sprints(project_path, src_dirs, has_tests)
    return sprints, has_tests
