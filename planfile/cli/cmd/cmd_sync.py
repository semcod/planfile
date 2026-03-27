"""Sync commands for planfile integrations."""

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path
import sys
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from planfile.integrations.config import IntegrationConfig
from planfile.sync.state import SyncState

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
    
    # Load tickets - try multiple sources
    from planfile.core.store import PlanfileStore
    store = PlanfileStore(directory)
    
    # Get tickets with integration filter
    all_tickets = []
    tickets_source = None
    
    # Try 1: New .planfile/ structure
    if store.is_initialized():
        tickets_source = ".planfile/ structure"
        sprint = store.load_sprint("current")
        if sprint:
            for ticket_id, ticket in sprint.get("tickets", {}).items():
                ticket_integration = ticket.get("integration", integration_name)
                if isinstance(ticket_integration, list):
                    if integration_name in ticket_integration:
                        all_tickets.append((ticket_id, ticket))
                elif ticket_integration == integration_name:
                    all_tickets.append((ticket_id, ticket))
        
        backlog = store.load_backlog()
        if backlog:
            for ticket_id, ticket in backlog.get("tickets", {}).items():
                ticket_integration = ticket.get("integration", integration_name)
                if isinstance(ticket_integration, list):
                    if integration_name in ticket_integration:
                        all_tickets.append((ticket_id, ticket))
                elif ticket_integration == integration_name:
                    all_tickets.append((ticket_id, ticket))
    
    # Try 2: Old format v1 (*.planfile.yaml files with sprint/backlog sections)
    if not all_tickets:
        import glob
        planfile_pattern = Path(directory) / "*.planfile.yaml"
        for planfile_path in glob.glob(str(planfile_pattern)):
            try:
                with open(planfile_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                # Check for old format v1 with sprint section
                if "sprint" in data and "tickets" in data.get("sprint", {}):
                    tickets_source = f"{Path(planfile_path).name} (sprint)"
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
                    for ticket_id, ticket in data["backlog"]["tickets"].items():
                        ticket_integration = ticket.get("integration", integration_name)
                        if isinstance(ticket_integration, list):
                            if integration_name in ticket_integration:
                                all_tickets.append((ticket_id, ticket))
                        elif ticket_integration == integration_name:
                            all_tickets.append((ticket_id, ticket))
            except Exception as e:
                console.print(f"[dim]⚠️ Could not load {planfile_path}: {e}[/dim]")
    
    if not all_tickets:
        console.print("[yellow]ℹ️ No tickets to sync[/yellow]")
        console.print("[dim]   Searched: .planfile/ structure and *.planfile.yaml files[/dim]")
        return
    
    console.print(f"📊 Found {len(all_tickets)} tickets for {integration_name} (source: {tickets_source})")
    
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
            sync_to_external(backend, all_tickets, dry_run, store, integration_name)
            progress.update(task, description="[green]✓ Synced to external system[/green]")
        
        if direction in ["from", "both"]:
            task = progress.add_task("Syncing from external system...", total=None)
            sync_from_external(backend, store, dry_run, integration_name)
            progress.update(task, description="[green]✓ Synced from external system[/green]")
    
    if not dry_run:
        console.print(f"\n✅ Sync with {integration_name} completed successfully")
    else:
        console.print(f"\n✅ Dry run completed for {integration_name}")


def sync_to_external(backend, tickets, dry_run: bool, store, integration_name: str):
    """Sync planfile tickets to external system."""
    # Initialize sync state
    sync_state = SyncState(Path(store.planfile_dir), integration_name)
    ticket_map = {}
    
    for ticket_id, ticket in tickets:
        if dry_run:
            console.print(f"  Would create/update: {ticket_id} - {ticket.get('title', 'No title')}")
        else:
            try:
                # Check if ticket already exists using sync state
                external_id = sync_state.get_remote_id(ticket_id) or ticket.get("external_id")
                if external_id:
                    # Update existing ticket
                    backend.update_ticket(external_id, ticket)
                    console.print(f"  ✓ Updated: {ticket_id} → {external_id}")
                else:
                    # Create new ticket
                    external_ticket = backend.create_ticket(ticket)
                    external_id = external_ticket.id if hasattr(external_ticket, 'id') else str(external_ticket.get('id'))
                    
                    # Store mapping in sync state
                    ticket_map[ticket_id] = external_id
                    
                    # Update ticket in store with external_id
                    ticket["external_id"] = external_id
                    ticket["backend"] = integration_name
                    
                    console.print(f"  ✓ Created: {ticket_id} → {external_id}")
            except Exception as e:
                console.print(f"  ✗ Failed to sync {ticket_id}: {e}")
    
    # Save sync state with new mappings
    if ticket_map and not dry_run:
        sync_state.save_sync(ticket_map)
        # Save updated store
        store.save_sprint("current", store.load_sprint("current"))
        store.save_backlog(store.load_backlog())


def sync_from_external(backend, store, dry_run: bool, integration_name: str):
    """Sync tickets from external system to planfile."""
    # Initialize sync state
    sync_state = SyncState(Path(store.planfile_dir), integration_name)
    imported_count = 0
    updated_count = 0
    
    try:
        external_tickets = backend.list_tickets()
        
        # Load current sprint and backlog
        sprint = store.load_sprint("current") or {"tickets": {}}
        backlog = store.load_backlog() or {"tickets": {}}
        
        for ext_ticket in external_tickets:
            ext_id = str(ext_ticket.get('id', ''))
            ext_title = ext_ticket.get('title', 'No title')
            
            # Check if already imported using sync state
            planfile_id = sync_state.get_local_id(ext_id)
            
            if dry_run:
                if planfile_id:
                    console.print(f"  Would update: {planfile_id} from {ext_id}")
                else:
                    console.print(f"  Would import: {ext_title}")
            else:
                try:
                    if planfile_id:
                        # Update existing ticket
                        if planfile_id in sprint.get("tickets", {}):
                            sprint["tickets"][planfile_id].update({
                                "status": ext_ticket.get("status", "open"),
                                "assignee": ext_ticket.get("assignee"),
                                "labels": ext_ticket.get("labels", []),
                            })
                        elif planfile_id in backlog.get("tickets", {}):
                            backlog["tickets"][planfile_id].update({
                                "status": ext_ticket.get("status", "open"),
                                "assignee": ext_ticket.get("assignee"),
                                "labels": ext_ticket.get("labels", []),
                            })
                        updated_count += 1
                        console.print(f"  ✓ Updated: {planfile_id} from {ext_id}")
                    else:
                        # Import new ticket - generate ID
                        new_id = f"{integration_name.upper()}-{ext_id}"
                        
                        # Create ticket data
                        ticket_data = {
                            "title": ext_title,
                            "description": ext_ticket.get("description", ""),
                            "status": ext_ticket.get("status", "open"),
                            "assignee": ext_ticket.get("assignee"),
                            "labels": ext_ticket.get("labels", []),
                            "external_id": ext_id,
                            "backend": integration_name,
                            "integration": integration_name,
                        }
                        
                        # Add to backlog by default
                        backlog["tickets"][new_id] = ticket_data
                        
                        # Save mapping in sync state
                        sync_state.save_sync({new_id: ext_id})
                        
                        imported_count += 1
                        console.print(f"  ✓ Imported: {new_id} ← {ext_id}")
                except Exception as e:
                    console.print(f"  ✗ Failed to import {ext_id}: {e}")
        
        # Save updated store
        if (imported_count > 0 or updated_count > 0) and not dry_run:
            store.save_sprint("current", sprint)
            store.save_backlog(backlog)
            console.print(f"\n📥 Imported {imported_count} new tickets, updated {updated_count} existing")
                
    except Exception as e:
        console.print(f"  ✗ Failed to import tickets: {e}")


def find_planfile_ticket(external_ticket, store, sync_state):
    """Find corresponding planfile ticket for external ticket using sync state."""
    ext_id = str(external_ticket.get('id', ''))
    
    # First check sync state
    local_id = sync_state.get_local_id(ext_id)
    if local_id:
        return local_id
    
    # Fallback: search by external_id in tickets
    ext_id_int = ext_id.lstrip('#')
    
    # Check sprint
    sprint = store.load_sprint("current")
    if sprint:
        for ticket_id, ticket in sprint.get("tickets", {}).items():
            if ticket.get("external_id") == ext_id or ticket.get("external_id") == ext_id_int:
                return ticket_id
    
    # Check backlog
    backlog = store.load_backlog()
    if backlog:
        for ticket_id, ticket in backlog.get("tickets", {}).items():
            if ticket.get("external_id") == ext_id or ticket.get("external_id") == ext_id_int:
                return ticket_id
    
    return None
