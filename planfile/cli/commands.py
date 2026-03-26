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

from planfile.models import Strategy
from planfile.runner import apply_strategy_to_tickets, run_strategy
from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.integrations.github import GitHubBackend
from planfile.integrations.jira import JiraBackend
from planfile.integrations.gitlab import GitLabBackend
from planfile.integrations.generic import GenericBackend
from . import auto_loop

app = typer.Typer(help="Strategy CLI - Manage strategies and sprints")
console = Console()
logger = logging.getLogger(__name__)

# Add auto subcommand
app.add_typer(auto_loop.app, name="auto", help="Automated CI/CD commands")

# Import and add extra commands
from .extra_commands import add_extra_commands
add_extra_commands(app)


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


def _execute_apply_strategy(
    strategy: Strategy,
    project_path: Path,
    backends: dict,
    dry_run: bool,
    sprint_ids: Optional[List[int]]
) -> dict:
    """Execute strategy application with progress bar."""
    with Progress() as progress:
        task = progress.add_task("Applying planfile...", total=100)
        
        results = apply_strategy_to_tickets(
            strategy=strategy,
            project_path=str(project_path),
            backends=backends,
            backend_name="default",
            dry_run=dry_run,
            sprint_filter=sprint_ids
        )
        
        progress.update(task, completed=100)
    
    return results


def _display_apply_results(results: dict) -> None:
    """Display strategy application results."""
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


def _save_results(results: dict, output: Optional[Path]) -> None:
    """Save results to file if specified."""
    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]✓[/green] Results saved to: {output}")


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
    strategy = _load_and_validate_strategy(strategy_path)
    
    # Load backend config
    backend_config = _load_backend_config(backend, config_file)
    
    # Validate config
    if not all(v for v in backend_config.values() if v is not None):
        console.print("[red]✗[/red] Missing backend configuration. Use --config-file or set environment variables.")
        raise typer.Exit(1)
    
    # Parse sprint filter
    sprint_ids = _parse_sprint_filter(sprint_filter)
    
    # Get backend
    backends = _select_backend(backend, backend_config)
    
    # Apply strategy
    results = _execute_apply_strategy(strategy, project_path, backends, dry_run, sprint_ids)
    
    # Display results
    _display_apply_results(results)
    
    # Save results
    _save_results(results, output)


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


@app.command("generate")
def generate_strategy_cli(
    project_path: str = typer.Argument(".", help="Project path to analyze"),
    output: str = typer.Option("strategy.yaml", help="Output file path"),
    model: Optional[str] = typer.Option(None, help="LiteLLM model ID"),
    sprints: int = typer.Option(3, help="Number of sprints to generate"),
    focus: Optional[str] = typer.Option(None, help="Focus area: complexity, duplication, tests, docs"),
    toon_dir: Optional[str] = typer.Option(None, help="Pre-existing .toon analysis directory"),
    dry_run: bool = typer.Option(False, help="Show prompt but don't call LLM"),
):
    """Generate strategy.yaml from project analysis + LLM."""
    from ..llm.generator import generate_strategy
    from ..loaders.yaml_loader import save_strategy_yaml

    try:
        console.print(f"[bold]Analyzing project:[/bold] {project_path}")
        
        strategy = generate_strategy(
            project_path,
            model=model,
            sprints=sprints,
            focus=focus,
            toon_dir=toon_dir,
            dry_run=dry_run,
        )

        if not dry_run:
            save_strategy_yaml(strategy, output)
            console.print(f"[green]✓[/green] Strategy saved to: {output}")
            console.print(f"  Sprints: {len(strategy.sprints)}")
            total_tasks = sum(len(s.task_patterns) for s in strategy.sprints)
            console.print(f"  Tasks: {total_tasks}")
            
            if strategy.quality_gates:
                console.print(f"  Quality Gates: {len(strategy.quality_gates)}")
    
    except Exception as e:
        console.print(f"[red]✗[/red] Generation failed: {e}")
        raise typer.Exit(1)


def main():
    """Main CLI entry point."""
    app()


@app.command("generate-from-files")
def generate_from_files_cmd(
    project_path: str = typer.Argument(".", help="Project path to analyze"),
    output: str = typer.Option("planfile-from-files.yaml", help="Output file path"),
    project_name: Optional[str] = typer.Option(None, help="Project name"),
    max_sprints: int = typer.Option(4, help="Maximum number of sprints"),
    focus: Optional[str] = typer.Option(None, help="Focus area: quality, security, performance, testing, documentation"),
    patterns: Optional[List[str]] = typer.Option(None, help="File patterns to analyze"),
    verbose: bool = typer.Option(False, help="Verbose output"),
):
    """Generate planfile from file analysis (no LLM required)."""
    from ..analysis.generator import generator
    from ..loaders.yaml_loader import save_strategy_yaml
    
    try:
        console.print(f"[bold]Analyzing project files:[/bold] {project_path}")
        
        if verbose:
            console.print(f"  Project name: {project_name or 'auto-detected'}")
            console.print(f"  Max sprints: {max_sprints}")
            console.print(f"  Focus area: {focus or 'auto-detected'}")
            if patterns:
                console.print(f"  Patterns: {', '.join(patterns)}")
        
        # Generate strategy from file analysis
        strategy = generator.generate_from_current_project(
            project_path=project_path,
            project_name=project_name,
            max_sprints=max_sprints,
            focus_area=focus,
            patterns=patterns
        )
        
        # Save strategy
        save_strategy_yaml(strategy, output)
        
        console.print(f"[green]✓[/green] Strategy saved to: {output}")
        
        # Show summary
        if isinstance(strategy, dict):
            console.print(f"  Name: {strategy.get('name', 'N/A')}")
            console.print(f"  Sprints: {len(strategy.get('sprints', []))}")
            
            total_issues = strategy.get('summary', {}).get('total_issues', 0)
            if total_issues > 0:
                console.print(f"  Issues found: {total_issues}")
            
            if strategy.get('quality_gates'):
                console.print(f"  Quality gates: {len(strategy['quality_gates'])}")
            
            # Show priority breakdown
            priority_breakdown = strategy.get('summary', {}).get('priority_breakdown', {})
            if priority_breakdown:
                console.print("\n[bold]Issue Breakdown:[/bold]")
                for priority, count in priority_breakdown.items():
                    color = {
                        'critical': 'red',
                        'high': 'yellow',
                        'medium': 'blue',
                        'low': 'green'
                    }.get(priority, 'white')
                    console.print(f"  {priority}: [{color}]{count}[/{color}]")
        
        console.print(f"\n[dim]Next steps:[/dim]")
        console.print(f"  1. Review: planfile validate {output}")
        console.print(f"  2. Apply: planfile apply {output} . --dry-run")
        console.print(f"  3. Execute: planfile apply {output} . --backend <backend>")
    
    except Exception as e:
        console.print(f"[red]✗[/red] Generation failed: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)
