import os
import json
import typer
from pathlib import Path
from typing import Optional, List
from rich.console import Console

from planfile.models import Strategy
from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.integrations.github import GitHubBackend
from planfile.integrations.jira import JiraBackend
from planfile.integrations.gitlab import GitLabBackend
from planfile.integrations.generic import GenericBackend
from planfile.sync.mock import MockBackend

console = Console()

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

def _load_and_validate_strategy(strategy_path: Path) -> Strategy:
    """Load and validate strategy file."""
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print(f"[green]✓[/green] Loaded strategy: {strategy.name}")
        return strategy
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load strategy: {e}")
        raise typer.Exit(1)

def _load_backend_config(backend: str, config_file: Optional[Path]) -> dict:
    """Load backend configuration from file or environment."""
    backend_config = {}
    
    if config_file:
        with open(config_file) as f:
            backend_config = json.load(f)
    else:
        if backend == "github":
            backend_config = {
                "repo": os.environ.get("GITHUB_REPO"),
                "token": os.environ.get("GITHUB_TOKEN")
            }
        elif backend == "jira":
            backend_config = {
                "base_url": os.environ.get("JIRA_URL"),
                "email": os.environ.get("JIRA_EMAIL"),
                "token": os.environ.get("JIRA_TOKEN"),
                "project": os.environ.get("JIRA_PROJECT")
            }
        elif backend == "gitlab":
            backend_config = {
                "url": os.environ.get("GITLAB_URL", "https://gitlab.com"),
                "token": os.environ.get("GITLAB_TOKEN"),
                "project_id": os.environ.get("GITLAB_PROJECT_ID")
            }
    
    return backend_config

def _parse_sprint_filter(sprint_filter: Optional[str]) -> Optional[List[int]]:
    """Parse sprint filter from string."""
    if not sprint_filter:
        return None
    
    try:
        return [int(s.strip()) for s in sprint_filter.split(",")]
    except ValueError:
        console.print("[red]✗[/red] Invalid sprint filter format. Use comma-separated integers.")
        raise typer.Exit(1)

def _select_backend(backend: str, backend_config: dict) -> dict:
    """Select and initialize backend."""
    try:
        backend_instance = get_backend(backend, backend_config)
        return {"default": backend_instance}
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize backend: {e}")
        raise typer.Exit(1)
