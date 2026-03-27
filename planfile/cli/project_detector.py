"""
Project auto-detection module for planfile init.

Detects project information from:
- pyproject.toml (Python projects)
- package.json (Node.js projects)
- README.md (project description)
- Directory structure (project type inference)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DetectedProject:
    """Container for detected project information."""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    project_type: Optional[str] = None  # api, web, cli, library
    domain: Optional[str] = None
    authors: list[str] = None
    license: Optional[str] = None
    source_dir: Optional[str] = None
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []


def _find_readme_description(project_path: Path) -> Optional[str]:
    """Extract first paragraph from README as description."""
    readme_files = ["README.md", "README.rst", "README.txt", "README"]
    
    for readme_name in readme_files:
        readme_path = project_path / readme_name
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                # Find first non-empty line that's not a header
                lines = content.split("\n")
                for line in lines:
                    line = line.strip()
                    # Skip empty lines, headers, and badges
                    if line and not line.startswith("#") and not line.startswith("["):
                        # Remove markdown formatting
                        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)  # links
                        line = re.sub(r"[*_`~]", "", line)  # formatting chars
                        if len(line) > 10:  # Meaningful description
                            return line[:200]  # Limit length
                return None
            except Exception:
                return None
    return None


def _detect_from_pyproject(project_path: Path) -> Optional[DetectedProject]:
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
    
    # If no description from pyproject, try README
    if not project.description:
        project.description = _find_readme_description(project_path)
    
    return project if project.name else None


def _detect_from_package_json(project_path: Path) -> Optional[DetectedProject]:
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
    
    # If no description, try README
    if not project.description:
        project.description = _find_readme_description(project_path)
    
    return project if project.name else None


def _infer_python_project_type(deps: list, pyproject_data: dict, project_path: Path) -> Optional[str]:
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


def _infer_node_project_type(deps: list, package_data: dict) -> Optional[str]:
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


def _detect_from_structure(project_path: Path) -> Optional[DetectedProject]:
    """Detect project info from directory structure only."""
    project = DetectedProject()
    
    # Use directory name as project name
    project.name = project_path.name.replace("-", " ").replace("_", " ").title()
    
    # Try to get description from README
    project.description = _find_readme_description(project_path)
    
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
    
    return project


def detect_project(project_path: Optional[Path] = None) -> DetectedProject:
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
    
    return {
        "name": detected.name or "",
        "description": detected.description or "",
        "version": detected.version or "1.0.0",
        "project_type": detected.project_type or "api",
        "domain": detected.domain or "software",
        "has_detection": bool(detected.name),
        "source": "pyproject.toml" if detected.name and (Path.cwd() / "pyproject.toml").exists()
                  else "package.json" if detected.name and (Path.cwd() / "package.json").exists()
                  else "README" if detected.description and not detected.name
                  else "structure",
    }
