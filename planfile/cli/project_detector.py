"""
Project auto-detection module for planfile init.

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

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


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


def _find_readme_description(project_path: Path) -> str | None:
    """Extract first paragraph from README as description."""
    desc, _ = _find_readme_content(project_path)
    return desc


def _find_readme_content(project_path: Path) -> tuple[str | None, str | None]:
    """
    Extract description and goal from README.
    Returns: (description, goal) - goal is first meaningful paragraph, description can be from badges/tagline
    """
    readme_files = ["README.md", "README.rst", "README.txt", "README"]

    for readme_name in readme_files:
        readme_path = project_path / readme_name
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                lines = content.split("\n")

                description = None
                goal = None

                # Find first non-empty, non-header line for description
                for line in lines:
                    line_stripped = line.strip()
                    # Skip empty lines, headers, and badges
                    if not line_stripped or line_stripped.startswith("#") or line_stripped.startswith("["):
                        continue
                    # Remove markdown formatting
                    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line_stripped)  # links
                    cleaned = re.sub(r"[*_`~]", "", cleaned)  # formatting chars
                    if len(cleaned) > 10:
                        description = cleaned[:200]
                        break

                # Find a better "goal" - look for summary/intro paragraph
                # Skip past badges and find first substantial paragraph
                content_without_badges = re.sub(r'\[!?\[.*?\]\(.*?\)\]\(.*?\)', '', content)
                content_without_badges = re.sub(r'!\[.*?\]\(.*?\)', '', content_without_badges)
                paragraphs = [p.strip() for p in content_without_badges.split('\n\n') if p.strip()]

                for para in paragraphs:
                    # Skip short lines (likely badges), headers, and code blocks
                    if len(para) < 20 or para.startswith('#') or para.startswith('```'):
                        continue
                    # Clean markdown
                    cleaned_para = re.sub(r"[*_`~]", "", para)
                    cleaned_para = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned_para)
                    if len(cleaned_para) > 30:
                        goal = cleaned_para[:150]
                        break

                return description, goal
            except Exception:
                return None, None
    return None, None


def _find_readme_goal(project_path: Path) -> str | None:
    """Extract goal/summary from README."""
    _, goal = _find_readme_content(project_path)
    return goal


def _detect_quality_gates(project_path: Path, pyproject_data: dict | None = None) -> list[DetectedQualityGate]:
    """Detect quality gates from project configuration files."""
    gates = []

    # Test configuration detection
    has_pytest = False
    has_test_dir = (project_path / "tests").exists() or (project_path / "test").exists()
    has_test_files = len(list(project_path.glob("test_*.py"))) > 0 or len(list(project_path.glob("*_test.py"))) > 0

    if pyproject_data:
        # Check for pytest in pyproject.toml
        if "tool" in pyproject_data and "pytest" in pyproject_data.get("tool", {}):
            has_pytest = True
        if "project" in pyproject_data and "dependencies" in pyproject_data["project"]:
            deps = [d.lower() for d in pyproject_data["project"]["dependencies"]]
            if any("pytest" in d for d in deps):
                has_pytest = True

    # Check for pytest.ini, setup.cfg, tox.ini
    if (project_path / "pytest.ini").exists():
        has_pytest = True
    if (project_path / "tox.ini").exists():
        has_pytest = True

    if has_test_dir or has_test_files or has_pytest:
        gates.append(DetectedQualityGate(
            name="Test Coverage",
            description="Minimum test coverage threshold",
            criteria=["pytest --cov >= 80%", "All tests passing"]
        ))

    # Docker detection
    if (project_path / "Dockerfile").exists() or (project_path / "docker-compose.yml").exists():
        gates.append(DetectedQualityGate(
            name="Docker Build",
            description="Docker image builds successfully",
            criteria=["docker build -t app . succeeds", "No build errors"]
        ))

    # CI/CD detection
    ci_cd_paths = [
        project_path / ".github" / "workflows",
        project_path / ".gitlab-ci.yml",
        project_path / ".circleci",
        project_path / "azure-pipelines.yml",
        project_path / "Jenkinsfile",
        project_path / ".travis.yml",
    ]
    has_ci = any(p.exists() for p in ci_cd_paths)

    if has_ci:
        gates.append(DetectedQualityGate(
            name="CI/CD Pipeline",
            description="Continuous integration checks pass",
            criteria=["All GitHub/GitLab checks passing", "Linting passes", "Tests pass in CI"]
        ))

    # Code quality tools detection
    quality_tools = []
    if (project_path / ".pre-commit-config.yaml").exists():
        quality_tools.append("pre-commit hooks")
    if (project_path / "ruff.toml").exists() or (project_path / "pyproject.toml").exists():
        if pyproject_data and "tool" in pyproject_data:
            if "ruff" in pyproject_data["tool"]:
                quality_tools.append("ruff linting")
    if (project_path / "mypy.ini").exists() or (project_path / ".mypy.ini").exists():
        quality_tools.append("mypy type checking")
    elif pyproject_data and "tool" in pyproject_data and "mypy" in pyproject_data["tool"]:
        quality_tools.append("mypy type checking")

    if quality_tools:
        gates.append(DetectedQualityGate(
            name="Code Quality",
            description="Code quality standards met",
            criteria=[f"{tool} passes" for tool in quality_tools]
        ))

    # Security tools detection
    security_tools = []
    if (project_path / ".bandit").exists() or (project_path / "bandit.yaml").exists():
        security_tools.append("bandit")
    if pyproject_data and "tool" in pyproject_data and "bandit" in pyproject_data["tool"]:
        security_tools.append("bandit")
    # Check for safety, pip-audit in dependencies
    if pyproject_data and "project" in pyproject_data:
        deps = [d.lower() for d in pyproject_data["project"].get("dependencies", [])]
        if any("safety" in d for d in deps):
            security_tools.append("dependency vulnerability scan")

    if security_tools:
        gates.append(DetectedQualityGate(
            name="Security Scan",
            description="Security checks pass",
            criteria=[f"{tool} scan passes" for tool in security_tools] + ["No critical vulnerabilities"]
        ))

    # Documentation detection
    if (project_path / "docs").exists() or (project_path / "documentation").exists():
        gates.append(DetectedQualityGate(
            name="Documentation",
            description="Documentation is built and valid",
            criteria=["Docs build without errors", "API docs generated"]
        ))

    return gates


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


def _detect_license(project_path: Path) -> str | None:
    """Detect license from LICENSE file."""
    license_files = ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"]

    for license_name in license_files:
        license_path = project_path / license_name
        if license_path.exists():
            try:
                content = license_path.read_text(encoding="utf-8", errors="ignore")
                # Common license detection
                if "MIT" in content[:500]:
                    return "MIT"
                elif "Apache" in content[:500]:
                    return "Apache-2.0"
                elif "GPL" in content[:500] or "GNU GENERAL PUBLIC LICENSE" in content[:500]:
                    return "GPL"
                elif "BSD" in content[:500]:
                    return "BSD"
                else:
                    return "Unknown"
            except Exception:
                return None
    return None


def _detect_git_authors(project_path: Path) -> list[str]:
    """Detect authors from git config."""
    authors = []

    try:
        # Try to get user name and email from git config
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            cwd=project_path
        )
        if result.returncode == 0:
            name = result.stdout.strip()

            result = subprocess.run(
                ["git", "config", "user.email"],
                capture_output=True,
                text=True,
                cwd=project_path
            )
            if result.returncode == 0:
                email = result.stdout.strip()
                authors.append(f"{name} <{email}>")
    except Exception:
        pass

    return authors


def _detect_model_tier(project_path: Path) -> str | None:
    """Detect preferred model tier from environment/config files."""

    # Check environment variables
    env_vars = [
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_KEY",
        "GOOGLE_API_KEY", "COHERE_API_KEY"
    ]

    for var in env_vars:
        if os.environ.get(var):
            # If premium API keys present, suggest balanced or premium
            if "ANTHROPIC" in var:
                return "balanced"  # Claude is good middle ground
            return "cheap"  # OpenAI cheap tier for cost-effective

    # Check .env files
    env_files = [".env", ".env.local", ".env.development"]
    for env_file in env_files:
        env_path = project_path / env_file
        if env_path.exists():
            try:
                content = env_path.read_text(encoding="utf-8")
                if "ANTHROPIC" in content or "CLAUDE" in content:
                    return "balanced"
                if "OPENAI" in content or "GPT" in content:
                    return "cheap"
            except Exception:
                pass

    # Check config files
    config_files = [
        project_path / "config.yaml",
        project_path / "config.yml",
        project_path / ".planfile" / "config.yaml",
    ]

    for config_path in config_files:
        if config_path.exists():
            try:
                content = config_path.read_text(encoding="utf-8")
                if "claude" in content.lower() or "opus" in content.lower():
                    return "premium"
                if "gpt-4" in content.lower():
                    return "balanced"
                if "local" in content.lower() or "ollama" in content.lower():
                    return "free"
            except Exception:
                pass

    return None


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


def _infer_python_project_type(deps: list, pyproject_data: dict, project_path: Path) -> str | None:
    """Infer Python project type from dependencies."""
    dep_names = [d.lower() for d in deps]

    # Check for FastAPI, Flask, Django, etc.
    if any(d in dep_names for d in ["fastapi", "flask", "django", "starlette", "tornado"]):
        return "api"

    # Check for web frameworks
    if any(d in dep_names for d in ["streamlit", "gradio", "dash", "bokeh"]):
        return "web"

    # Check for CLI frameworks
    if any(d in dep_names for d in ["typer", "click", "argparse", "fire", "docopt"]):
        return "cli"

    # Check for project scripts (CLI entry points)
    if "project" in pyproject_data and "scripts" in pyproject_data["project"]:
        scripts = pyproject_data["project"]["scripts"]
        if scripts and len(scripts) > 0:
            return "cli"

    # Check directory structure
    src_path = project_path / "src"
    if src_path.exists():
        subdirs = [d.name for d in src_path.iterdir() if d.is_dir()]
        if len(subdirs) == 1:
            return "library"

    # Check for main module vs package
    py_files = list(project_path.glob("*.py"))
    if len(py_files) == 1:
        return "cli"

    return "library"  # Default for Python


def _infer_node_project_type(deps: list, package_data: dict) -> str | None:
    """Infer Node.js project type from dependencies."""
    dep_names = [d.lower() for d in deps]

    # Check for API frameworks
    if any(d in dep_names for d in ["express", "fastify", "koa", "hapi", "restify", "nestjs"]):
        return "api"

    # Check for frontend frameworks
    if any(d in dep_names for d in ["react", "vue", "angular", "svelte", "next", "nuxt"]):
        return "web"

    # Check for CLI tools
    if any(d in dep_names for d in ["commander", "yargs", "inquirer", "oclif"]):
        return "cli"

    # Check bin field
    if package_data.get("bin"):
        return "cli"

    return "web"  # Default for Node.js


def _infer_domain(keywords: list, classifiers: list, description: str) -> str:
    """Infer business domain from keywords and description."""
    text = " ".join(keywords + classifiers + [description]).lower()

    domain_keywords = {
        "e-commerce": ["e-commerce", "ecommerce", "shop", "store", "cart", "payment", "stripe", "paypal"],
        "finance": ["finance", "fintech", "banking", "payment", "trading", "crypto", "bitcoin", "ethereum"],
        "healthcare": ["health", "medical", "healthcare", "patient", "clinic", "hospital"],
        "devtools": ["dev", "developer", "tool", "cli", "sdk", "api", "framework", "library"],
        "data": ["data", "analytics", "ml", "machine learning", "ai", "visualization", "database"],
        "security": ["security", "auth", "authentication", "cryptography", "encryption", "oauth"],
        "communication": ["chat", "messaging", "communication", "notification", "email", "slack"],
        "media": ["media", "video", "audio", "image", "streaming", "content"],
    }

    for domain, keywords_list in domain_keywords.items():
        if any(kw in text for kw in keywords_list):
            return domain

    return "software"  # Default


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
