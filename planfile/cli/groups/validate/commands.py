"""Validate command handlers for planfile CLI."""

from __future__ import annotations

from pathlib import Path

import typer

from planfile.cli.core import console, print_error
from planfile.core.schema import SchemaValidator, validate_yaml_file
from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.testql_integration import (
    build_testql_tickets,
    run_testql_validation,
    sync_testql_tickets,
    upsert_testql_tickets,
)


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
        raise typer.Exit(1) from e


def validate_schema_cli(
    file_path: Path = typer.Argument(None, help="Path to YAML file (default: planfile.yaml)"),
    file_type: str = typer.Option("auto", help="File type: auto, planfile, sprint"),
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Validate YAML file schema version and structure."""
    from planfile import Planfile

    # Auto-detect file path if not provided
    if file_path is None:
        pf = Planfile.auto_discover(".")
        file_path = Path(pf.store.project_dir) / "planfile.yaml"
        file_type = "planfile"

    # Auto-detect file type
    if file_type == "auto":
        if "redsl" in file_path.name:
            file_type = "redsl"
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


def validate_testql_cli(
    scenario_path: Path = typer.Argument(..., help="Path to .testql.toon.yaml scenario"),
    project_path: Path = typer.Option(Path("."), "--project", "-p", help="Project root path"),
    url: str = typer.Option("http://localhost:8101", "--url", help="Base API URL for TestQL"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate/parse scenario without full execution"),
    strategy_path: str = typer.Option("planfile.yaml", "--strategy", "-s", help="Target planfile YAML"),
    create_tickets: bool = typer.Option(True, "--create-tickets/--no-create-tickets", help="Create planfile tickets for TestQL failures"),
    sync_targets: bool = typer.Option(True, "--sync/--no-sync", help="Sync generated tickets to TODO.md and configured integrations"),
    max_tickets: int = typer.Option(25, "--max-tickets", help="Maximum number of tickets generated from one TestQL run"),
    testql_bin: str = typer.Option("testql", "--testql-bin", help="TestQL CLI executable name/path"),
    testql_repo_path: Path = typer.Option(Path("/home/tom/github/oqlos/testql"), "--testql-repo-path", help="Fallback path to local TestQL repository"),
) -> None:
    """Validate changes via TestQL DSL and optionally generate/sync tickets."""
    report = run_testql_validation(
        scenario_path=scenario_path,
        project_path=project_path,
        url=url,
        dry_run=dry_run,
        quiet=True,
        testql_bin=testql_bin,
        testql_repo_path=testql_repo_path,
    )

    console.print(f"[bold]TestQL scenario:[/bold] {report.get('source')}")
    console.print(
        f"[dim]Result:[/dim] ok={report.get('ok')} "
        f"passed={report.get('passed')} failed={report.get('failed')} "
        f"exit_code={report.get('exit_code')}"
    )

    if report.get("warnings"):
        console.print(f"[yellow]Warnings:[/yellow] {len(report.get('warnings') or [])}")

    tickets: list[dict] = []
    if create_tickets and not bool(report.get("ok")):
        tickets = build_testql_tickets(report, scenario_path, max_tickets=max_tickets)
        if tickets:
            upsert_report = upsert_testql_tickets(
                strategy_path=strategy_path,
                tickets=tickets,
                project_path=project_path,
            )
            console.print(
                f"[cyan]Tickets:[/cyan] created={upsert_report.get('created', 0)} "
                f"skipped={upsert_report.get('skipped', 0)} "
                f"strategy={upsert_report.get('strategy_path')}"
            )

            if sync_targets:
                sync_report = sync_testql_tickets(tickets, project_path=project_path, include_configured=True)
                for integration in sync_report.get("integrations", []):
                    console.print(
                        f"[dim]sync {integration.get('integration')}:[/dim] "
                        f"created={integration.get('created', 0)} "
                        f"skipped={integration.get('skipped', 0)} "
                        f"failed={integration.get('failed', 0)}"
                    )
        else:
            console.print("[dim]No ticket candidates generated from TestQL report.[/dim]")

    if not bool(report.get("ok")):
        raise typer.Exit(1)
