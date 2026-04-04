"""Directory structure analysis for sprint suggestions."""

from __future__ import annotations

from pathlib import Path


def _analyze_directory_structure(project_path: Path) -> tuple[list[dict], bool]:
    """
    Analyze directory structure and suggest sprint structure.
    Returns: (suggested_sprints, has_tests)
    """
    sprints = []
    has_tests = False

    # Check for tests
    if (project_path / "tests").exists() or (project_path / "test").exists():
        has_tests = True

    # Check for source directories
    src_dirs = []
    if (project_path / "src").exists():
        src_path = project_path / "src"
        src_dirs = [d.name for d in src_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
    elif (project_path / project_path.name.replace('-', '_').replace(' ', '_')).exists():
        src_dirs = [project_path.name.replace('-', '_').replace(' ', '_')]
    else:
        # Find main Python/JS directories
        py_dirs = [d.name for d in project_path.iterdir() if d.is_dir() and d.name != "venv" and d.name != ".venv"
                   and not d.name.startswith('.') and not d.name.startswith('__')]
        if py_dirs:
            src_dirs = py_dirs[:3]  # Limit to first 3

    # Suggest sprint structure based on findings
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

    return sprints, has_tests
