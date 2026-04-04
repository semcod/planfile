"""Apply command handlers for planfile CLI."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import typer
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from planfile.cli.core import console, print_error
from planfile.cli.groups.apply.utils import (
    load_and_validate_strategy,
    load_backend_config,
    parse_sprint_filter,
    select_backend,
)
from planfile.models import Strategy
from planfile.runner import apply_strategy_to_tickets


def execute_apply_strategy(
    strategy: Strategy,
    project_path: Path,
    backend: str,
    dry_run: bool,
    sprint_ids: list[int] | None
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


def display_apply_results(results: dict) -> None:
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


def save_results(results: dict, output: Path | None) -> None:
    """Save results to file if specified."""
    if output:
        with open(output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n[green]✓[/green] Results saved to: {output}")


def apply_strategy_cli(
    strategy_path: Path = typer.Argument(..., help="Path to strategy YAML file"),
    project_path: Path = typer.Argument(..., help="Path to project directory"),
    backend: str = typer.Option("github", help="Backend type (github, jira, gitlab, generic)"),
    config_file: Path | None = typer.Option(None, help="Backend config file"),
    dry_run: bool = typer.Option(False, help="Simulate without creating tickets"),
    sprint_filter: str | None = typer.Option(None, help="Comma-separated sprint IDs to process"),
    output: Path | None = typer.Option(None, help="Output results to file"),
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Apply a strategy to create tickets."""
    if verbose:
        logging.basicConfig(level=logging.INFO)

    strategy = load_and_validate_strategy(strategy_path)
    backend_config = load_backend_config(backend, config_file)

    # Mock backend doesn't need configuration
    if backend != "mock" and not all(v for v in backend_config.values() if v is not None):
        print_error("Missing backend configuration. Use --config-file or set environment variables.")
        raise typer.Exit(1)

    sprint_ids = parse_sprint_filter(sprint_filter)
    backends = select_backend(backend, backend_config)
    results = execute_apply_strategy(strategy, project_path, backend, dry_run, sprint_ids)
    display_apply_results(results)
    save_results(results, output)
