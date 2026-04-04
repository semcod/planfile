"""Core sync logic for planfile CLI."""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.progress import Progress, SpinnerColumn, TextColumn

from planfile.cli.core import console, print_error, print_warning
from planfile.integrations.config import IntegrationConfig
from planfile.sync.operations import sync_from_external, sync_to_external


def _initialize_backend(
    integration_name: str,
    config: IntegrationConfig,
    show_header: bool
) -> Any:
    """Initialize and validate backend for sync operation."""
    # Special handling for markdown backend (default when no integrations configured)
    if integration_name == "markdown":
        backend = config.get_default_backend()
        if show_header:
            console.print("✅ Using default markdown backend (CHANGELOG.md, TODO.md)")
        return backend

    # Validate integration for other backends
    if not config.validate_integration(integration_name):
        print_error(f"{integration_name} integration not configured or invalid")
        raise typer.Exit(1)

    # Get backend
    try:
        backend = config.get_integration_backend(integration_name)
        if show_header:
            console.print(f"✅ Connected to {integration_name}")
    except Exception as e:
        print_error(f"Failed to connect to {integration_name}: {e}")
        raise typer.Exit(1)

    return backend


def _ticket_matches_integration(ticket: dict, integration_name: str) -> bool:
    """Check if ticket matches the given integration."""
    ticket_integration = ticket.get("integration")
    if not ticket_integration:
        return False
    if isinstance(ticket_integration, list):
        return integration_name in ticket_integration
    return ticket_integration == integration_name


def _collect_tickets_from_sprint(
    sprint: dict | None,
    integration_name: str
) -> list[tuple[str, dict]]:
    """Collect tickets from sprint matching integration."""
    if not sprint:
        return []
    tickets = []
    for ticket_id, ticket in sprint.get("tickets", {}).items():
        if _ticket_matches_integration(ticket, integration_name):
            tickets.append((ticket_id, ticket))
    return tickets


def _collect_tickets_from_backlog(
    backlog: dict | None,
    integration_name: str
) -> list[tuple[str, dict]]:
    """Collect tickets from backlog matching integration."""
    if not backlog:
        return []
    tickets = []
    for ticket_id, ticket in backlog.get("tickets", {}).items():
        if _ticket_matches_integration(ticket, integration_name):
            tickets.append((ticket_id, ticket))
    return tickets


def _load_tickets_v1_format(
    directory: str,
    integration_name: str
) -> tuple[list[tuple[str, dict]], str | None, str | None, dict | None]:
    """Load tickets from v1 format (*.planfile.yaml files)."""
    all_tickets = []
    tickets_source = None
    v1_source_file = None
    v1_data = None

    planfile_pattern = Path(directory) / "*.planfile.yaml"
    for planfile_path in glob.glob(str(planfile_pattern)):
        try:
            with open(planfile_path) as f:
                data = yaml.safe_load(f) or {}

            # Check for old format v1 with sprint section
            if "sprint" in data and "tickets" in data.get("sprint", {}):
                tickets_source = f"{Path(planfile_path).name} (sprint)"
                v1_source_file = planfile_path
                v1_data = data
                for ticket_id, ticket in data["sprint"]["tickets"].items():
                    ticket_integration = ticket.get("integration", integration_name)
                    if isinstance(ticket_integration, list):
                        if integration_name in ticket_integration:
                            all_tickets.append((ticket_id, ticket))
                    elif ticket_integration == integration_name:
                        all_tickets.append((ticket_id, ticket))

            # Check for backlog section
            if "backlog" in data and "tickets" in data.get("backlog", {}):
                if tickets_source is None:
                    tickets_source = f"{Path(planfile_path).name} (backlog)"
                    v1_source_file = planfile_path
                    v1_data = data
                for ticket_id, ticket in data["backlog"]["tickets"].items():
                    ticket_integration = ticket.get("integration", integration_name)
                    if isinstance(ticket_integration, list):
                        if integration_name in ticket_integration:
                            all_tickets.append((ticket_id, ticket))
                    elif ticket_integration == integration_name:
                        all_tickets.append((ticket_id, ticket))
        except Exception as e:
            console.print(f"[dim]⚠️ Could not load {planfile_path}: {e}[/dim]")

    return all_tickets, tickets_source, v1_source_file, v1_data


def _load_tickets_for_sync(
    store: Any,
    directory: str,
    integration_name: str
) -> tuple[list[tuple[str, dict]], str | None, str | None, dict | None]:
    """Load tickets from all sources for sync operation."""
    tickets_source = None
    v1_source_file = None
    v1_data = None
    all_tickets = []

    # Try 1: New .planfile/ structure
    if store.is_initialized():
        tickets_source = ".planfile/ structure"
        sprint = store.load_sprint("current")
        all_tickets.extend(_collect_tickets_from_sprint(sprint, integration_name))
        backlog = store.load_backlog()
        all_tickets.extend(_collect_tickets_from_backlog(backlog, integration_name))

    # Try 2: Old format v1 (*.planfile.yaml files with sprint/backlog sections)
    if not all_tickets:
        v1_tickets, tickets_source, v1_source_file, v1_data = _load_tickets_v1_format(
            directory, integration_name
        )
        all_tickets.extend(v1_tickets)

    return all_tickets, tickets_source, v1_source_file, v1_data


def _execute_sync_with_progress(
    backend: Any,
    all_tickets: list[tuple[str, dict]],
    dry_run: bool,
    store: Any,
    integration_name: str,
    v1_source_file: str | None,
    v1_data: dict | None,
    direction: str
) -> None:
    """Execute sync with progress bar."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        if direction in ["to", "both"]:
            task = progress.add_task("Syncing to external system...", total=None)
            sync_to_external(backend, all_tickets, dry_run, store, integration_name, v1_source_file, v1_data)
            progress.update(task, description="[green]✓ Synced to external system[/green]")

        if direction in ["from", "both"]:
            task = progress.add_task("Syncing from external system...", total=None)
            sync_from_external(backend, store, dry_run, integration_name, v1_source_file, v1_data)
            progress.update(task, description="[green]✓ Synced from external system[/green]")


def sync_integration(
    integration_name: str,
    directory: str,
    dry_run: bool,
    direction: str,
    show_header: bool = True
) -> None:
    """Sync with a specific integration."""
    if show_header:
        console.print(f"🔄 Syncing with {integration_name}...")

    # Load configuration
    config = IntegrationConfig(directory)
    config.load_configs()

    # Initialize backend
    backend = _initialize_backend(integration_name, config, show_header)

    # Load tickets from all sources
    from planfile.core.store import PlanfileStore
    store = PlanfileStore(directory)
    all_tickets, tickets_source, v1_source_file, v1_data = _load_tickets_for_sync(
        store, directory, integration_name
    )

    if not all_tickets:
        print_warning("No tickets to sync")
        console.print("[dim]   Searched: .planfile/ structure and *.planfile.yaml files[/dim]")
        return

    console.print(f"📊 Found {len(all_tickets)} tickets for {integration_name} (source: {tickets_source})")

    if dry_run:
        console.print("\n[cyan]🔍 DRY RUN - No changes will be made[/cyan]")

    # Execute sync with progress
    _execute_sync_with_progress(
        backend, all_tickets, dry_run, store, integration_name,
        v1_source_file, v1_data, direction
    )

    if not dry_run:
        console.print(f"\n✅ Sync with {integration_name} completed successfully")
    else:
        console.print(f"\n✅ Dry run completed for {integration_name}")
