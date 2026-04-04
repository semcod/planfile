"""Sync operations - bidirectional ticket synchronization with external systems."""

from __future__ import annotations

import traceback
from pathlib import Path

from rich.console import Console

from planfile.sync.state import SyncState

console = Console()


def sync_to_external(backend, tickets, dry_run: bool, store, integration_name: str, v1_source_file=None, v1_data=None) -> None:
    """Sync planfile tickets to external system."""
    sync_state = SyncState(Path(store.planfile_dir), integration_name)
    ticket_map = {}

    for ticket_id, ticket in tickets:
        if dry_run:
            console.print(f"  Would create/update: {ticket_id} - {ticket.get('title', 'No title')}")
        else:
            try:
                external_id = sync_state.get_remote_id(ticket_id) or ticket.get("external_id")
                if external_id:
                    _update_existing_ticket(backend, ticket, ticket_id, external_id, integration_name, sync_state)
                else:
                    _create_new_ticket(backend, ticket, ticket_id, integration_name, sync_state, ticket_map)
            except Exception as e:
                console.print(f"  ✗ Failed to sync {ticket_id}: {e}")
                if "403" not in str(e) and "Forbidden" not in str(e):
                    console.print(f"    [dim]Error details: {traceback.format_exc()}[/dim]")

    if not dry_run:
        sync_state.save_sync(ticket_map)
        _save_sync_results(store, v1_source_file, v1_data)


def _update_existing_ticket(backend, ticket, ticket_id: str, external_id: str, integration_name: str, sync_state) -> None:
    """Update an existing ticket in the external system."""
    try:
        backend.update_ticket(external_id, ticket)
        console.print(f"  ✓ Updated: {ticket_id} → {external_id}")
    except Exception as e:
        if "404" in str(e) or "Not Found" in str(e):
            console.print(f"  ⚠️  Issue not found, creating new: {external_id}")
            external_ticket = backend.create_ticket(ticket)
            new_id = external_ticket.id if hasattr(external_ticket, 'id') else str(external_ticket.get('id'))
            console.print(f"  ✓ Created: {ticket_id} → {new_id}")
        elif _is_permission_error(e):
            _print_permission_error(ticket_id)
            raise Exception("GitHub token lacks required permissions. See instructions above.")
        else:
            raise


def _create_new_ticket(backend, ticket, ticket_id: str, integration_name: str, sync_state, ticket_map: dict) -> None:
    """Create a new ticket in the external system."""
    try:
        external_ticket = backend.create_ticket(ticket)
        external_id = external_ticket.id if hasattr(external_ticket, 'id') else str(external_ticket.get('id'))
    except Exception as e:
        if _is_permission_error(e):
            _print_permission_error(ticket_id)
            raise Exception("GitHub token lacks required permissions. See instructions above.")
        else:
            raise

    ticket_map[ticket_id] = external_id
    ticket["external_id"] = external_id
    ticket["backend"] = integration_name
    console.print(f"  ✓ Created: {ticket_id} → {external_id}")


def _is_permission_error(e: Exception) -> bool:
    """Check if exception is a permission-related error."""
    err_str = str(e).lower()
    return "403" in str(e) or "Forbidden" in str(e) or "not accessible by personal access token" in err_str


def _print_permission_error(ticket_id: str) -> None:
    """Print permission error instructions."""
    console.print(f"[red]❌ GitHub permission denied for {ticket_id}[/red]")
    console.print("[yellow]🔑 Your GitHub token lacks permission to create issues[/yellow]")
    console.print("[yellow]📝 To fix this:[/yellow]")
    console.print("[yellow]   1. Go to: https://github.com/settings/tokens[/yellow]")
    console.print("[yellow]   2. Click 'Generate new token (classic)'[/yellow]")
    console.print("[yellow]   3. Select 'repo' scope (or 'public_repo' for public repos)[/yellow]")
    console.print("[yellow]   4. Copy the new token[/yellow]")
    console.print("[yellow]   5. Update your .env file with the new token[/yellow]")
    console.print("[yellow]   6. Try again: planfile sync github[/yellow]")


def _save_sync_results(store, v1_source_file, v1_data) -> None:
    """Save sync results to appropriate storage."""
    from planfile.sync.utils import save_v1_format

    if v1_source_file and v1_data:
        save_v1_format(v1_source_file, v1_data)
        console.print(f"  💾 Saved changes to {Path(v1_source_file).name}")
    else:
        store.save_sprint("current", store.load_sprint("current"))
        store.save_backlog(store.load_backlog())


def sync_from_external(backend, store, dry_run: bool, integration_name: str, v1_source_file=None, v1_data=None) -> None:
    """Sync tickets from external system to planfile."""
    sync_state = SyncState(Path(store.planfile_dir), integration_name)
    imported_count = 0
    updated_count = 0

    if v1_source_file and v1_data:
        sprint = v1_data.get("sprint", {"tickets": {}})
        backlog = v1_data.get("backlog", {"tickets": {}})
    else:
        sprint = store.load_sprint("current") or {"tickets": {}}
        backlog = store.load_backlog() or {"tickets": {}}

    try:
        external_tickets = backend.list_tickets()

        if external_tickets is None:
            console.print(f"  [dim]ℹ️ No tickets found in {integration_name}[/dim]")
            return

        external_tickets = list(external_tickets)

        if not external_tickets:
            console.print(f"  [dim]ℹ️ No tickets to import from {integration_name}[/dim]")
            return

        for ext_ticket in external_tickets:
            ext_data = _extract_ticket_data(ext_ticket)
            planfile_id = sync_state.get_local_id(ext_data['id'])

            if dry_run:
                _print_dry_run_action(planfile_id, ext_data)
            else:
                try:
                    if planfile_id:
                        updated_count = _update_local_ticket(sprint, backlog, planfile_id, ext_data, updated_count)
                    else:
                        imported_count = _import_new_ticket(backlog, ext_data, integration_name, sync_state, imported_count)
                except Exception as e:
                    console.print(f"  ✗ Failed to import {ext_data['id']}: {e}")

        if not dry_run and (imported_count > 0 or updated_count > 0):
            _save_import_results(store, v1_source_file, v1_data, sprint, backlog, imported_count, updated_count)

    except Exception as e:
        console.print(f"  ✗ Failed to import tickets: {e}")
        console.print(f"    [dim]{traceback.format_exc()}[/dim]")


def _extract_ticket_data(ext_ticket) -> dict:
    """Extract standardized ticket data from external ticket (dict or Pydantic model)."""
    if hasattr(ext_ticket, 'id'):
        return {
            'id': str(ext_ticket.id),
            'title': ext_ticket.title if hasattr(ext_ticket, 'title') else 'No title',
            'status': ext_ticket.status if hasattr(ext_ticket, 'status') else 'open',
            'assignee': ext_ticket.assignee if hasattr(ext_ticket, 'assignee') else None,
            'labels': ext_ticket.labels if hasattr(ext_ticket, 'labels') else [],
            'description': ext_ticket.description if hasattr(ext_ticket, 'description') else '',
        }
    else:
        return {
            'id': str(ext_ticket.get('id', '')),
            'title': ext_ticket.get('title', 'No title'),
            'status': ext_ticket.get('status', 'open'),
            'assignee': ext_ticket.get('assignee'),
            'labels': ext_ticket.get('labels', []),
            'description': ext_ticket.get('description', ''),
        }


def _print_dry_run_action(planfile_id: str | None, ext_data: dict) -> None:
    """Print dry-run action for a ticket."""
    if planfile_id:
        console.print(f"  Would update: {planfile_id} from {ext_data['id']}")
    else:
        console.print(f"  Would import: {ext_data['title']}")


def _update_local_ticket(sprint: dict, backlog: dict, planfile_id: str, ext_data: dict, updated_count: int) -> int:
    """Update an existing local ticket from external data."""
    update_fields = {
        "status": ext_data['status'],
        "assignee": ext_data['assignee'],
        "labels": ext_data['labels'],
    }

    if planfile_id in sprint.get("tickets", {}):
        sprint["tickets"][planfile_id].update(update_fields)
    elif planfile_id in backlog.get("tickets", {}):
        backlog["tickets"][planfile_id].update(update_fields)

    console.print(f"  ✓ Updated: {planfile_id} from {ext_data['id']}")
    return updated_count + 1


def _import_new_ticket(backlog: dict, ext_data: dict, integration_name: str, sync_state, imported_count: int) -> int:
    """Import a new ticket from external system."""
    new_id = f"{integration_name.upper()}-{ext_data['id']}"

    ticket_data = {
        "title": ext_data['title'],
        "description": ext_data['description'],
        "status": ext_data['status'],
        "assignee": ext_data['assignee'],
        "labels": ext_data['labels'],
        "external_id": ext_data['id'],
        "backend": integration_name,
        "integration": integration_name,
    }

    backlog["tickets"][new_id] = ticket_data
    sync_state.save_sync({new_id: ext_data['id']})

    console.print(f"  ✓ Imported: {new_id} ← {ext_data['id']}")
    return imported_count + 1


def _save_import_results(store, v1_source_file, v1_data, sprint, backlog, imported_count, updated_count) -> None:
    """Save import results to appropriate storage."""
    from planfile.sync.utils import save_v1_format

    if v1_source_file and v1_data:
        if "sprint" in v1_data:
            v1_data["sprint"] = sprint
        if "backlog" in v1_data:
            v1_data["backlog"] = backlog
        save_v1_format(v1_source_file, v1_data)
        console.print(f"\n💾 Saved {imported_count} imported, {updated_count} updated to {Path(v1_source_file).name}")
    else:
        store.save_sprint("current", sprint)
        store.save_backlog(backlog)
        console.print(f"\n📥 Imported {imported_count} new tickets, updated {updated_count} existing")
