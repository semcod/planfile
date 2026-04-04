"""Review command utilities."""

import json
import os
from pathlib import Path

from planfile.cli.core import console
from planfile.integrations.generic import GenericBackend
from planfile.integrations.github import GitHubBackend
from planfile.integrations.gitlab import GitLabBackend
from planfile.integrations.jira import JiraBackend
from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.models import Strategy
from planfile.sync.mock import MockBackend

BACKEND_REGISTRY = {
    "github": GitHubBackend,
    "jira": JiraBackend,
    "gitlab": GitLabBackend,
    "generic": GenericBackend,
    "mock": MockBackend
}


def get_backend(backend_type: str, config: dict):
    """Get backend instance by type and config."""
    backend_class = BACKEND_REGISTRY.get(backend_type)
    if not backend_class:
        raise ValueError(f"Unknown backend type: {backend_type}")

    if backend_type == "github":
        return backend_class(repo=config["repo"], token=config.get("token"))
    elif backend_type == "jira":
        return backend_class(base_url=config["base_url"], email=config.get("email"), token=config.get("token"), project=config.get("project"))
    elif backend_type == "gitlab":
        return backend_class(url=config.get("url", "https://gitlab.com"), token=config.get("token"), project_id=config.get("project_id"))
    elif backend_type == "generic":
        return backend_class(base_url=config["base_url"], api_key=config.get("api_key"), headers=config.get("headers"))
    elif backend_type == "mock":
        return backend_class()


def _load_backend_config(backend: str, config_file: Path | None) -> dict:
    """Load backend configuration from file or environment."""
    if config_file:
        with open(config_file) as f:
            return json.load(f)

    # Default configs from environment
    if backend == "github":
        return {
            "repo": os.environ.get("GITHUB_REPO", ""),
            "token": os.environ.get("GITHUB_TOKEN")
        }
    elif backend == "jira":
        return {
            "base_url": os.environ.get("JIRA_URL", ""),
            "email": os.environ.get("JIRA_EMAIL"),
            "token": os.environ.get("JIRA_TOKEN"),
            "project": os.environ.get("JIRA_PROJECT")
        }
    elif backend == "gitlab":
        return {
            "url": os.environ.get("GITLAB_URL", "https://gitlab.com"),
            "token": os.environ.get("GITLAB_TOKEN"),
            "project_id": os.environ.get("GITLAB_PROJECT_ID")
        }
    elif backend == "generic":
        return {
            "base_url": os.environ.get("GENERIC_BACKEND_URL", ""),
            "api_key": os.environ.get("GENERIC_API_KEY"),
            "headers": {}
        }

    return {}


def _load_and_validate_strategy(strategy_path: Path) -> Strategy:
    """Load and validate strategy file."""
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print(f"[green]✓[/green] Loaded strategy: {strategy.name}")
        return strategy
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load strategy: {e}")
        raise
