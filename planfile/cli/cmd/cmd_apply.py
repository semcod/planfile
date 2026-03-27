import json
import typer
import logging
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

from planfile.models import Strategy
from planfile.runner import apply_strategy_to_tickets
from planfile.cli.cmd.cmd_utils import (
    _load_and_validate_strategy,
    _load_backend_config,
    _parse_sprint_filter,
    _select_backend
)

console = Console()

def _execute_apply_strategy(
    strategy: Strategy,
    project_path: Path,
    backend: str,
    dry_run: bool,
    sprint_ids: Optional[List[int]]
) -> dict:
    """Execute strategy application with progress bar."""
    with Progress() as progress:
        task = progress.add_task("Applying planfile...", total=100)
        
        results = apply_strategy_to_tickets(
            strategy=strategy,
            project_path=str(project_path),
            backend=backend,
            dry_run=dry_run
        )
        
        progress.update(task, completed=100)
    
    return results

def _display_apply_results(results: dict) -> None:
    """Display strategy application results."""
    console.print("\n[bold]Strategy Applied Successfully![/bold]")
    console.print(Panel(
        f"Created: {len(results['created'])}\n"
        f"Updated: {len(results['updated'])}\n"
        f"Errors: {len(results['errors'])}\n"
        f"Dry Run: {results['dry_run']}",
        title="Summary"
    ))
    
    if results["created"]:
        table = Table(title="Created Tickets")
        table.add_column("Sprint", style="cyan")
        table.add_column("Task", style="magenta")
        table.add_column("Title", style="green")
        table.add_column("Type", style="blue")
        table.add_column("Priority", style="yellow")
        
        for ticket in results["created"]:
            table.add_row(
                str(ticket["sprint"]),
                ticket["pattern"],
                ticket["title"],
                ticket["type"],
                ticket["priority"]
            )
        
        console.print(table)
    
    if results["errors"]:
        console.print("\n[red]Errors:[/red]")
        for error in results["errors"]:
            console.print(f"  • {error}")

def _save_results(results: dict, output: Optional[Path]) -> None:
    """Save results to file if specified."""
    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]✓[/green] Results saved to: {output}")

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
    
    strategy = _load_and_validate_strategy(strategy_path)
    backend_config = _load_backend_config(backend, config_file)
    
    # Mock backend doesn't need configuration
    if backend != "mock" and not all(v for v in backend_config.values() if v is not None):
        console.print("[red]✗[/red] Missing backend configuration. Use --config-file or set environment variables.")
        raise typer.Exit(1)
    
    sprint_ids = _parse_sprint_filter(sprint_filter)
    backends = _select_backend(backend, backend_config)
    results = _execute_apply_strategy(strategy, project_path, backend, dry_run, sprint_ids)
    _display_apply_results(results)
    _save_results(results, output)
