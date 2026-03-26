import typer
import os
import json
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
import logging

from ..models import Strategy
from ..runner import apply_strategy, review_strategy
from ..loaders.yaml_loader import load_strategy_yaml
from ..integrations.github import GitHubBackend
from ..integrations.jira import JiraBackend
from ..integrations.gitlab import GitLabBackend
from ..integrations.generic import GenericBackend

app = typer.Typer(help="Strategy CLI - Manage strategies and sprints")
console = Console()
logger = logging.getLogger(__name__)


def get_backend(backend_type: str, config: dict):
    """Get backend instance by type and config."""
    if backend_type == "github":
        return GitHubBackend(
            repo=config["repo"],
            token=config.get("token")
        )
    elif backend_type == "jira":
        return JiraBackend(
            base_url=config["base_url"],
            email=config.get("email"),
            token=config.get("token"),
            project=config.get("project")
        )
    elif backend_type == "gitlab":
        return GitLabBackend(
            url=config.get("url", "https://gitlab.com"),
            token=config.get("token"),
            project_id=config.get("project_id")
        )
    elif backend_type == "generic":
        return GenericBackend(
            base_url=config["base_url"],
            api_key=config.get("api_key"),
            headers=config.get("headers")
        )
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


@app.command("apply")
def apply_strategy_cli(
    strategy_path: Path = typer.Argument(..., help="Path to strategy YAML file"),
    project_path: Path = typer.Argument(..., help="Path to project directory"),
    backend: str = typer.Option("github", help="Backend type (github, jira, gitlab, generic)"),
    config_file: Optional[Path] = typer.Option(None, help="Backend config file"),
    dry_run: bool = typer.Option(False, help="Simulate without creating tickets"),
    sprint_filter: Optional[str] = typer.Option(None, help="Comma-separated sprint IDs to process"),
    output: Optional[Path] = typer.Option(None, help="Output results to file"),
    verbose: bool = typer.Option(False, help="Verbose output"),
):
    """Apply a strategy to create tickets."""
    
    if verbose:
        logging.basicConfig(level=logging.INFO)
    
    # Load strategy
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print(f"[green]✓[/green] Loaded strategy: {planfile.name}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load strategy: {e}")
        raise typer.Exit(1)
    
    # Load backend config
    backend_config = {}
    if config_file:
        with open(config_file) as f:
            backend_config = json.load(f)
    else:
        # Try to get from environment
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
    
    # Validate config
    if not all(v for v in backend_config.values() if v is not None):
        console.print("[red]✗[/red] Missing backend configuration. Use --config-file or set environment variables.")
        raise typer.Exit(1)
    
    # Parse sprint filter
    sprint_ids = None
    if sprint_filter:
        try:
            sprint_ids = [int(s.strip()) for s in sprint_filter.split(",")]
        except ValueError:
            console.print("[red]✗[/red] Invalid sprint filter format. Use comma-separated integers.")
            raise typer.Exit(1)
    
    # Get backend
    try:
        backend_instance = get_backend(backend, backend_config)
        backends = {"default": backend_instance}
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize backend: {e}")
        raise typer.Exit(1)
    
    # Apply strategy
    with Progress() as progress:
        task = progress.add_task("Applying planfile...", total=100)
        
        results = apply_strategy(
            strategy=strategy,
            project_path=str(project_path),
            backends=backends,
            backend_name="default",
            dry_run=dry_run,
            sprint_filter=sprint_ids
        )
        
        progress.update(task, completed=100)
    
    # Display results
    console.print("\n[bold]Strategy Applied Successfully![/bold]")
    console.print(Panel(
        f"Strategy: {results['strategy']}\n"
        f"Backend: {results['backend']}\n"
        f"Created: {results['summary']['created']}\n"
        f"Updated: {results['summary']['updated']}\n"
        f"Errors: {results['summary']['errors']}",
        title="Summary"
    ))
    
    # Show tickets table
    if results["tickets"]:
        table = Table(title="Created/Updated Tickets")
        table.add_column("Sprint", style="cyan")
        table.add_column("Task", style="magenta")
        table.add_column("Ticket ID", style="green")
        table.add_column("URL", style="blue")
        
        for key, ticket in results["tickets"].items():
            table.add_row(
                key.split("-")[1],
                key.split("-")[3],
                ticket.id,
                ticket.url or "N/A"
            )
        
        console.print(table)
    
    # Save results
    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]✓[/green] Results saved to: {output}")


@app.command("review")
def review_strategy_cli(
    strategy_path: Path = typer.Argument(..., help="Path to strategy YAML file"),
    project_path: Path = typer.Argument(..., help="Path to project directory"),
    backend: str = typer.Option("github", help="Backend type (github, jira, gitlab, generic)"),
    config_file: Optional[Path] = typer.Option(None, help="Backend config file"),
    output: Optional[Path] = typer.Option(None, help="Output results to file"),
    verbose: bool = typer.Option(False, help="Verbose output"),
):
    """Review strategy execution and progress."""
    
    if verbose:
        logging.basicConfig(level=logging.INFO)
    
    # Load strategy
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print(f"[green]✓[/green] Loaded strategy: {planfile.name}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load strategy: {e}")
        raise typer.Exit(1)
    
    # Load backend config (same as apply)
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
    
    # Get backend
    try:
        backend_instance = get_backend(backend, backend_config)
        backends = {"default": backend_instance}
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize backend: {e}")
        raise typer.Exit(1)
    
    # Review strategy
    results = review_strategy(
        strategy=strategy,
        project_path=str(project_path),
        backends=backends,
        backend_name="default"
    )
    
    # Display results
    console.print("\n[bold]Strategy Review Results[/bold]")
    
    # Summary panel
    summary = results["summary"]
    console.print(Panel(
        f"Total Tickets: {summary['total_tickets']}\n"
        f"Completed: {summary['completed']}\n"
        f"In Progress: {summary['in_progress']}\n"
        f"Not Started: {summary['not_started']}\n"
        f"Blocked: {summary['blocked']}",
        title="Progress Summary"
    ))
    
    # Progress metrics
    if "progress" in results.get("metrics", {}):
        progress_metrics = results["metrics"]["progress"]
        console.print("\n[bold]Progress Metrics:[/bold]")
        console.print(f"Completion Rate: {progress_metrics['completion_rate']:.1%}")
        console.print(f"In Progress Rate: {progress_metrics['in_progress_rate']:.1%}")
        console.print(f"Blocked Rate: {progress_metrics['blocked_rate']:.1%}")
    
    # Sprint status table
    if results["sprints"]:
        table = Table(title="Sprint Status")
        table.add_column("Sprint", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Tickets", style="blue")
        table.add_column("Completed", style="magenta")
        
        for sprint_id, sprint_data in results["sprints"].items():
            total = len(sprint_data["tickets"])
            completed = sum(
                1 for t in sprint_data["tickets"].values()
                if t["status"] in ["done", "completed", "closed"]
            )
            
            table.add_row(
                f"Sprint {sprint_id}: {sprint_data['name']}",
                sprint_data["status"],
                str(total),
                f"{completed}/{total}"
            )
        
        console.print(table)
    
    # Save results
    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]✓[/green] Results saved to: {output}")


@app.command("validate")
def validate_strategy_cli(
    strategy_path: Path = typer.Argument(..., help="Path to strategy YAML file"),
    verbose: bool = typer.Option(False, help="Verbose output"),
):
    """Validate a strategy YAML file."""
    
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print(f"[green]✓[/green] Strategy is valid!")
        console.print(f"Name: {planfile.name}")
        console.print(f"Project Type: {planfile.project_type}")
        console.print(f"Domain: {planfile.domain}")
        console.print(f"Sprints: {len(planfile.sprints)}")
        console.print(f"Task Patterns: {sum(len(patterns) for patterns in planfile.tasks.values())}")
        
        if verbose:
            console.print("\n[bold]Sprints:[/bold]")
            for sprint in planfile.sprints:
                console.print(f"  - Sprint {sprint.id}: {sprint.name} ({sprint.length_days} days)")
            
            console.print("\n[bold]Task Patterns:[/bold]")
            for category, patterns in planfile.tasks.items():
                console.print(f"  {category}:")
                for pattern in patterns:
                    console.print(f"    - {pattern.id}: {pattern.title}")
    
    except Exception as e:
        console.print(f"[red]✗[/red] Validation failed: {e}")
        raise typer.Exit(1)


def main():
    """Main CLI entry point."""
    app()
