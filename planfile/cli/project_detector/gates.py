"""Quality gate detection from project files."""

from __future__ import annotations

from pathlib import Path

from .base import DetectedQualityGate


def _detect_test_gates(project_path: Path, pyproject_data: dict | None) -> DetectedQualityGate | None:
    """Detect test configuration quality gates."""
    has_test_dir = (project_path / "tests").exists() or (project_path / "test").exists()
    has_test_files = len(list(project_path.glob("test_*.py"))) > 0 or len(list(project_path.glob("*_test.py"))) > 0

    if not has_test_dir and not has_test_files:
        return None

    has_pytest = _has_pytest_config(project_path, pyproject_data)

    if has_test_dir or has_test_files or has_pytest:
        return DetectedQualityGate(
            name="Test Coverage",
            description="Minimum test coverage threshold",
            criteria=["pytest --cov >= 80%", "All tests passing"]
        )
    return None


def _has_pytest_config(project_path: Path, pyproject_data: dict | None) -> bool:
    """Check if pytest is configured in the project."""
    if pyproject_data:
        if "tool" in pyproject_data and "pytest" in pyproject_data.get("tool", {}):
            return True
        deps = pyproject_data.get("project", {}).get("dependencies", [])
        if any("pytest" in d.lower() for d in deps):
            return True
    return (project_path / "pytest.ini").exists() or (project_path / "tox.ini").exists()


def _detect_docker_gates(project_path: Path) -> DetectedQualityGate | None:
    """Detect Docker quality gates."""
    if (project_path / "Dockerfile").exists() or (project_path / "docker-compose.yml").exists():
        return DetectedQualityGate(
            name="Docker Build",
            description="Docker image builds successfully",
            criteria=["docker build -t app . succeeds", "No build errors"]
        )
    return None


def _detect_ci_gates(project_path: Path) -> DetectedQualityGate | None:
    """Detect CI/CD quality gates."""
    ci_cd_paths = [
        project_path / ".github" / "workflows",
        project_path / ".gitlab-ci.yml",
        project_path / ".circleci",
        project_path / "azure-pipelines.yml",
        project_path / "Jenkinsfile",
        project_path / ".travis.yml",
    ]
    if any(p.exists() for p in ci_cd_paths):
        return DetectedQualityGate(
            name="CI/CD Pipeline",
            description="Continuous integration checks pass",
            criteria=["All GitHub/GitLab checks passing", "Linting passes", "Tests pass in CI"]
        )
    return None


def _detect_quality_tool_gates(project_path: Path, pyproject_data: dict | None) -> DetectedQualityGate | None:
    """Detect code quality tool gates."""
    quality_tools = _find_quality_tools(project_path, pyproject_data)
    if quality_tools:
        return DetectedQualityGate(
            name="Code Quality",
            description="Code quality standards met",
            criteria=[f"{tool} passes" for tool in quality_tools]
        )
    return None


def _find_quality_tools(project_path: Path, pyproject_data: dict | None) -> list[str]:
    """Find configured quality tools in the project."""
    tools = []
    if (project_path / ".pre-commit-config.yaml").exists():
        tools.append("pre-commit hooks")
    if _has_ruff_config(project_path, pyproject_data):
        tools.append("ruff linting")
    if _has_mypy_config(project_path, pyproject_data):
        tools.append("mypy type checking")
    return tools


def _has_ruff_config(project_path: Path, pyproject_data: dict | None) -> bool:
    """Check if ruff is configured."""
    if (project_path / "ruff.toml").exists():
        return True
    if pyproject_data and "tool" in pyproject_data:
        return "ruff" in pyproject_data["tool"]
    return False


def _has_mypy_config(project_path: Path, pyproject_data: dict | None) -> bool:
    """Check if mypy is configured."""
    if (project_path / "mypy.ini").exists() or (project_path / ".mypy.ini").exists():
        return True
    if pyproject_data and "tool" in pyproject_data:
        return "mypy" in pyproject_data["tool"]
    return False


def _detect_security_gates(project_path: Path, pyproject_data: dict | None) -> DetectedQualityGate | None:
    """Detect security tool gates."""
    security_tools = _find_security_tools(project_path, pyproject_data)
    if security_tools:
        return DetectedQualityGate(
            name="Security Scan",
            description="Security checks pass",
            criteria=[f"{tool} scan passes" for tool in security_tools] + ["No critical vulnerabilities"]
        )
    return None


def _find_security_tools(project_path: Path, pyproject_data: dict | None) -> list[str]:
    """Find configured security tools."""
    tools = []
    if _has_bandit_config(project_path, pyproject_data):
        tools.append("bandit")
    if pyproject_data and "project" in pyproject_data:
        deps = [d.lower() for d in pyproject_data["project"].get("dependencies", [])]
        if any("safety" in d for d in deps):
            tools.append("dependency vulnerability scan")
    return tools


def _has_bandit_config(project_path: Path, pyproject_data: dict | None) -> bool:
    """Check if bandit is configured."""
    if (project_path / ".bandit").exists() or (project_path / "bandit.yaml").exists():
        return True
    if pyproject_data and "tool" in pyproject_data:
        return "bandit" in pyproject_data["tool"]
    return False


def _detect_doc_gates(project_path: Path) -> DetectedQualityGate | None:
    """Detect documentation quality gates."""
    if (project_path / "docs").exists() or (project_path / "documentation").exists():
        return DetectedQualityGate(
            name="Documentation",
            description="Documentation is built and valid",
            criteria=["Docs build without errors", "API docs generated"]
        )
    return None


def _detect_quality_gates(project_path: Path, pyproject_data: dict | None = None) -> list[DetectedQualityGate]:
    """Detect quality gates from project configuration files."""
    gates = []
    detectors = [
        _detect_test_gates(project_path, pyproject_data),
        _detect_docker_gates(project_path),
        _detect_ci_gates(project_path),
        _detect_quality_tool_gates(project_path, pyproject_data),
        _detect_security_gates(project_path, pyproject_data),
        _detect_doc_gates(project_path),
    ]
    for gate in detectors:
        if gate:
            gates.append(gate)
    return gates
