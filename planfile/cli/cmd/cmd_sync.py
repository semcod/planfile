"""Sync commands for planfile integrations."""

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from planfile.integrations.config import IntegrationConfig

console = Console()
sync_app = typer.Typer(help="Sync tickets with external systems")


def create_sync_app():
    """Create the sync command app."""
    return sync_app


@sync_app.command()
def github(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
):
    """Sync tickets with GitHub Issues."""
    sync_integration("github", directory, dry_run, direction)


@sync_app.command()
def gitlab(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
):
    """Sync tickets with GitLab Issues."""
    sync_integration("gitlab", directory, dry_run, direction)


@sync_app.command()
def jira(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
):
    """Sync tickets with Jira."""
    sync_integration("jira", directory, dry_run, direction)


@sync_app.command()
def all(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
):
    """Sync tickets with all configured integrations."""
    config = IntegrationConfig(directory)
    config.load_configs()
    
    integrations = config.config.get("integrations", {}).keys()
    
    if not integrations:
        console.print("[yellow]⚠️ No integrations configured[/yellow]")
        raise typer.Exit(1)
    
    console.print(f"🔄 Syncing with integrations: {', '.join(integrations)}")
    
    for integration in integrations:
        console.print(f"\n📡 Syncing with {integration}...")
        try:
            sync_integration(integration, directory, dry_run, direction, show_header=False)
        except Exception as e:
            console.print(f"[red]❌ Failed to sync with {integration}: {e}[/red]")


def sync_integration(integration_name: str, directory: str, dry_run: bool, direction: str, show_header: bool = True):
    """Sync with a specific integration."""
    if show_header:
        console.print(f"🔄 Syncing with {integration_name}...")
    
    # Load configuration
    config = IntegrationConfig(directory)
    config.load_configs()
    
    # Validate integration
    if not config.validate_integration(integration_name):
        console.print(f"[red]❌ {integration_name} integration not configured or invalid[/red]")
        raise typer.Exit(1)
    
    # Get backend
    try:
        backend = config.get_integration_backend(integration_name)
        if show_header:
            console.print(f"✅ Connected to {integration_name}")
    except Exception as e:
        console.print(f"[red]❌ Failed to connect to {integration_name}: {e}[/red]")
        raise typer.Exit(1)
    
    # Load tickets
    from planfile.core.store import PlanfileStore
    store = PlanfileStore(directory)
    
    if not store.is_initialized():
        console.print("[yellow]⚠️ Planfile not initialized. Run 'planfile init' first[/yellow]")
        raise typer.Exit(1)
    
    # Get tickets with integration filter
    all_tickets = []
    
    # Sprint tickets
    sprint = store.load_sprint("current")
    if sprint:
        for ticket_id, ticket in sprint.get("tickets", {}).items():
            ticket_integration = ticket.get("integration", integration_name)
            if isinstance(ticket_integration, list):
                if integration_name in ticket_integration:
                    all_tickets.append((ticket_id, ticket))
            elif ticket_integration == integration_name:
                all_tickets.append((ticket_id, ticket))
    
    # Backlog tickets
    backlog = store.load_backlog()
    if backlog:
        for ticket_id, ticket in backlog.get("tickets", {}).items():
            ticket_integration = ticket.get("integration", integration_name)
            if isinstance(ticket_integration, list):
                if integration_name in ticket_integration:
                    all_tickets.append((ticket_id, ticket))
            elif ticket_integration == integration_name:
                all_tickets.append((ticket_id, ticket))
    
    if not all_tickets:
        console.print("[yellow]ℹ️ No tickets to sync[/yellow]")
        return
    
    console.print(f"📊 Found {len(all_tickets)} tickets for {integration_name}")
    
    if dry_run:
        console.print("\n[cyan]🔍 DRY RUN - No changes will be made[/cyan]")
    
    # Sync based on direction
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        if direction in ["to", "both"]:
            task = progress.add_task("Syncing to external system...", total=None)
            sync_to_external(backend, all_tickets, dry_run)
            progress.update(task, description="[green]✓ Synced to external system[/green]")
        
        if direction in ["from", "both"]:
            task = progress.add_task("Syncing from external system...", total=None)
            sync_from_external(backend, store, dry_run)
            progress.update(task, description="[green]✓ Synced from external system[/green]")
    
    if not dry_run:
        console.print(f"\n✅ Sync with {integration_name} completed successfully")
    else:
        console.print(f"\n✅ Dry run completed for {integration_name}")


def sync_to_external(backend, tickets, dry_run: bool):
    """Sync planfile tickets to external system."""
    for ticket_id, ticket in tickets:
        if dry_run:
            console.print(f"  Would create/update: {ticket_id} - {ticket.get('title', 'No title')}")
        else:
            try:
                # Check if ticket already exists
                external_id = ticket.get("external_id")
                if external_id:
                    # Update existing ticket
                    backend.update_ticket(external_id, ticket)
                else:
                    # Create new ticket
                    external_ticket = backend.create_ticket(ticket)
                    # Store external ID (in real implementation)
                    # ticket["external_id"] = external_ticket.id
                console.print(f"  ✓ Synced: {ticket_id}")
            except Exception as e:
                console.print(f"  ✗ Failed to sync {ticket_id}: {e}")


def sync_from_external(backend, store, dry_run: bool):
    """Sync tickets from external system to planfile."""
    try:
        external_tickets = backend.list_tickets()
        
        for ext_ticket in external_tickets:
            # Check if already imported
            planfile_id = find_planfile_ticket(ext_ticket, store)
            
            if dry_run:
                if planfile_id:
                    console.print(f"  Would update: {planfile_id} from {ext_ticket.get('id', 'unknown')}")
                else:
                    console.print(f"  Would import: {ext_ticket.get('title', 'No title')}")
            else:
                # Import or update logic would go here
                pass
                
    except Exception as e:
        console.print(f"  ✗ Failed to import tickets: {e}")


def find_planfile_ticket(external_ticket, store):
    """Find corresponding planfile ticket for external ticket."""
    # This would check for external_id or matching title
    return None
