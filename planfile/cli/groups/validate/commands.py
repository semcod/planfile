"""Validate command handlers for planfile CLI."""

from __future__ import annotations

from pathlib import Path

import typer

from planfile.cli.core import console, print_error
from planfile.core.schema import SchemaValidator, validate_yaml_file
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
                        console.print(f"    - {pattern.id}: {pattern.name}")

    except Exception as e:
        print_error(f"Validation failed: {e}")
        raise typer.Exit(1)


def validate_schema_cli(
    file_path: Path = typer.Argument(None, help="Path to YAML file (default: planfile.yaml)"),
    file_type: str = typer.Option("auto", help="File type: auto, planfile, sprint"),
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Validate YAML file schema version and structure."""
    from planfile import Planfile
    
    # Auto-detect file path if not provided
    if file_path is None:
        pf = Planfile.auto_discover()
        file_path = Path(pf.store.project_dir) / "planfile.yaml"
        file_type = "planfile"
    
    # Auto-detect file type
    if file_type == "auto":
        if "sprint" in file_path.name.lower() or file_path.parent.name == "sprints":
            file_type = "sprint"
        else:
            file_type = "planfile"
    
    console.print(f"[bold]Validating:[/bold] {file_path} (type: {file_type})")
    
    # Show current schema version
    current_version = SchemaValidator.get_current_schema_version()
    console.print(f"[bold]Current schema version:[/bold] {current_version}")
    
    # Validate file
    is_valid, errors = validate_yaml_file(file_path, file_type)
    
    if is_valid:
        console.print("[green]✓[/green] Schema validation passed!")
        
        if verbose and file_type == "planfile":
            with open(file_path) as f:
                import yaml
                data = yaml.safe_load(f)
                if "schema" in data:
                    console.print(f"[bold]File schema version:[/bold] {data['schema']}")
    else:
        console.print("[red]✗[/red] Schema validation failed!")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)
