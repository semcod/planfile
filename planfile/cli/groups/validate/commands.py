"""Validate command handlers for planfile CLI."""

from __future__ import annotations

from pathlib import Path

import typer

from planfile.cli.core import console, print_error
from planfile.loaders.yaml_loader import load_strategy_yaml


def validate_strategy_cli(
    strategy_path: Path = typer.Argument(..., help="Path to strategy YAML file"),
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Validate a strategy YAML file."""
    try:
        strategy = load_strategy_yaml(strategy_path)
        console.print("[green]✓[/green] Strategy is valid!")
        console.print(f"Name: {strategy.name}")
        console.print(f"Project Type: {strategy.project_type}")
        console.print(f"Domain: {strategy.domain}")
        console.print(f"Sprints: {len(strategy.sprints)}")
        tasks_dict = getattr(strategy, 'tasks', {}) or {}
        console.print(f"Task Patterns: {sum(len(v) for v in tasks_dict.values())}")

        if verbose:
            console.print("\n[bold]Sprints:[/bold]")
            for sprint in strategy.sprints:
                console.print(f"  - Sprint {sprint.id}: {sprint.name} ({sprint.length_days} days)")

            if tasks_dict:
                console.print("\n[bold]Task Patterns:[/bold]")
                for category, patterns in tasks_dict.items():
                    console.print(f"  {category}:")
                    for pattern in patterns:
                        console.print(f"    - {pattern.id}: {pattern.title}")

    except Exception as e:
        print_error(f"Validation failed: {e}")
        raise typer.Exit(1)
