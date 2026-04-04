"""Project type and domain inference helpers."""

from __future__ import annotations

from pathlib import Path


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
