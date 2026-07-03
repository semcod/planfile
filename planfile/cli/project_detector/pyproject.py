from pathlib import Path

from .base import DetectedProject
from .gates import _detect_quality_gates
from .git import _detect_git_authors
from .inference import _infer_domain, _infer_python_project_type
from .license import _detect_license
from .model_tier import _detect_model_tier
from .readme import _find_readme_description, _find_readme_goal
from .structure import _analyze_directory_structure


def _import_toml_loader() -> object | None:
    """Import a TOML loader compatible with the current Python runtime."""
    try:
        import tomllib

        return tomllib
    except ImportError:
        try:
            import tomli as tomllib

            return tomllib
        except ImportError:
            return None


def _load_pyproject_data(pyproject_path: Path) -> dict | None:
    """Load and parse pyproject.toml data."""
    tomllib = _import_toml_loader()
    if tomllib is None:
        return None
    try:
        with open(pyproject_path, 'rb') as f:
            return tomllib.load(f)
    except Exception:
        return None


def _populate_project_metadata(project: DetectedProject, data: dict) -> None:
    """Populate project metadata from PEP 621 project data."""
    proj = data['project']
    project.name = proj.get('name')
    project.description = proj.get('description')
    project.version = proj.get('version')
    project.license = proj.get('license', {}).get('text') if isinstance(proj.get('license'), dict) else proj.get('license')
    if 'authors' in proj:
        for author in proj['authors']:
            if isinstance(author, dict):
                name = author.get('name', '')
                email = author.get('email', '')
                if name and email:
                    project.authors.append(f'{name} <{email}>')
                elif name:
                    project.authors.append(name)


def _populate_poetry_metadata(project: DetectedProject, data: dict) -> None:
    """Populate project metadata from Poetry configuration."""
    poetry = data['tool']['poetry']
    project.name = poetry.get('name')
    project.description = poetry.get('description')
    project.version = poetry.get('version')
    if poetry.get('authors'):
        project.authors.extend(poetry['authors'])


def _populate_project_from_data(project: DetectedProject, data: dict) -> None:
    """Populate project fields from parsed pyproject data."""
    if 'project' in data:
        _populate_project_metadata(project, data)
    if not project.name and 'tool' in data and ('poetry' in data['tool']):
        _populate_poetry_metadata(project, data)


def _get_project_dependencies(data: dict) -> list:
    """Extract project dependencies from supported pyproject formats."""
    deps = []
    if 'project' in data and 'dependencies' in data['project']:
        deps = data['project']['dependencies']
    elif 'tool' in data and 'poetry' in data['tool'] and ('dependencies' in data['tool']['poetry']):
        deps = list(data['tool']['poetry']['dependencies'].keys())
    return deps


def _populate_inferred_project_details(project: DetectedProject, data: dict, project_path: Path) -> None:
    """Populate fields inferred from dependencies and repository contents."""
    deps = _get_project_dependencies(data)
    project.project_type = _infer_python_project_type(deps, data, project_path)
    if 'project' in data:
        keywords = data['project'].get('keywords', [])
        classifiers = data['project'].get('classifiers', [])
        project.domain = _infer_domain(keywords, classifiers, project.description or '')
    project.quality_gates = _detect_quality_gates(project_path, data)


def _populate_readme_and_repository_details(project: DetectedProject, project_path: Path) -> None:
    """Populate details inferred from README and repository structure."""
    if not project.description:
        project.description = _find_readme_description(project_path)
    project.goal = _find_readme_goal(project_path)
    project.suggested_sprints, project.has_tests = _analyze_directory_structure(project_path)
    project.has_docker = (project_path / 'Dockerfile').exists()
    project.has_ci_cd = any([(project_path / '.github' / 'workflows').exists(), (project_path / '.gitlab-ci.yml').exists()])
    if not project.license:
        project.license = _detect_license(project_path)
    if not project.authors:
        project.authors = _detect_git_authors(project_path)
    project.model_tier = _detect_model_tier(project_path)


def _detect_from_pyproject(project_path: Path) -> DetectedProject | None:
    """Detect project info from pyproject.toml."""
    pyproject_path = project_path / 'pyproject.toml'
    if not pyproject_path.exists():
        return None
    data = _load_pyproject_data(pyproject_path)
    if data is None:
        return None
    project = DetectedProject()
    _populate_project_from_data(project, data)
    _populate_inferred_project_details(project, data, project_path)
    _populate_readme_and_repository_details(project, project_path)
    return project if project.name else None
