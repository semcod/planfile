import json
import typer
import logging
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.runner import review_strategy
from planfile.cli.cmd.cmd_utils import _load_backend_config, get_backend

console = Console()

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
    
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print(f"[green]✓[/green] Loaded strategy: {strategy.name}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load strategy: {e}")
        raise typer.Exit(1)
    
    backend_config = _load_backend_config(backend, config_file)
    
    try:
        backend_instance = get_backend(backend, backend_config)
        backends = {"default": backend_instance}
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize backend: {e}")
        raise typer.Exit(1)
    
    results = review_strategy(
        strategy=strategy,
        project_path=str(project_path),
        backends=backends,
        backend_name="default"
    )
    
    console.print("\n[bold]Strategy Review Results[/bold]")
    
    summary = results["summary"]
    console.print(Panel(
        f"Total Tickets: {summary['total_tickets']}\n"
        f"Completed: {summary['completed']}\n"
        f"In Progress: {summary['in_progress']}\n"
        f"Not Started: {summary['not_started']}\n"
        f"Blocked: {summary['blocked']}",
        title="Progress Summary"
    ))
    
    if "progress" in results.get("metrics", {}):
        progress_metrics = results["metrics"]["progress"]
        console.print("\n[bold]Progress Metrics:[/bold]")
        console.print(f"Completion Rate: {progress_metrics['completion_rate']:.1%}")
        console.print(f"In Progress Rate: {progress_metrics['in_progress_rate']:.1%}")
        console.print(f"Blocked Rate: {progress_metrics['blocked_rate']:.1%}")
    
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
    
    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]✓[/green] Results saved to: {output}")
