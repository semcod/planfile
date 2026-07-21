"""Sync operations - bidirectional ticket synchronization with external systems."""

from __future__ import annotations

import traceback
from pathlib import Path

from rich.console import Console

from planfile.sync.state import SyncState

console = Console()


def sync_to_external(
    backend, tickets, dry_run: bool, store, integration_name: str, v1_source_file=None, v1_data=None
) -> None:
    """Sync planfile tickets to external system."""
    sync_state = SyncState(Path(store.base_dir), integration_name)
    ticket_map = {}

    for ticket_id, ticket in tickets:
        if dry_run:
            ticket_name = ticket.get("name") or ticket.get("title", "No title")
            console.print(f"  Would create/update: {ticket_id} - {ticket_name}")
        else:
            try:
                external_id = _ticket_external_id(ticket, ticket_id, integration_name, sync_state)
                if external_id:
                    _update_existing_ticket(
                        backend, ticket, ticket_id, external_id, integration_name, sync_state
                    )
                else:
                    _create_new_ticket(
                        backend, ticket, ticket_id, integration_name, sync_state, ticket_map
                    )
            except Exception as e:
                console.print(f"  ✗ Failed to sync {ticket_id}: {e}")
                if "403" not in str(e) and "Forbidden" not in str(e):
                    console.print(f"    [dim]Error details: {traceback.format_exc()}[/dim]")

    if not dry_run:
        sync_state.save_sync(ticket_map)
        _save_sync_results(store, v1_source_file, v1_data)


def _ticket_external_id(
    ticket: dict, ticket_id: str, integration_name: str, sync_state
) -> str | None:
    """Resolve an ID for one backend without leaking another backend's legacy ID."""
    state_id = sync_state.get_remote_id(ticket_id)
    if state_id:
        return str(state_id)
    backend_sync = (ticket.get("sync") or {}).get(integration_name) or {}
    if isinstance(backend_sync, dict) and backend_sync.get("id"):
        return str(backend_sync["id"])
    if ticket.get("backend") == integration_name and ticket.get("external_id"):
        return str(ticket["external_id"])
    return None


def _backend_ticket_payload(ticket: dict, ticket_id: str) -> dict:
    payload = dict(ticket)
    metadata = dict(payload.get("metadata") or {})
    metadata.setdefault("planfile_id", ticket_id)
    payload["metadata"] = metadata
    return payload


def _update_existing_ticket(
    backend, ticket, ticket_id: str, external_id: str, integration_name: str, sync_state
) -> None:
    """Update an existing ticket in the external system."""
    try:
        backend.update_ticket(
            external_id,
            name=ticket.get("name") or ticket.get("title"),
            body=ticket.get("description", "") or ticket.get("body", ""),
            status=ticket.get("status"),
            labels=ticket.get("labels"),
            priority=ticket.get("priority"),
            assignee=ticket.get("assignee"),
        )
        console.print(f"  ✓ Updated: {ticket_id} → {external_id}")
    except Exception as e:
        if "404" in str(e) or "Not Found" in str(e):
            console.print(f"  ⚠️  Issue not found, creating new: {external_id}")
            external_ticket = backend.create_ticket(_backend_ticket_payload(ticket, ticket_id))
            new_id = (
                external_ticket.id
                if hasattr(external_ticket, "id")
                else str(external_ticket.get("id"))
            )
            sync_state.save_sync({ticket_id: new_id})
            _record_backend_ref(ticket, integration_name, external_ticket, new_id)
            console.print(f"  ✓ Created: {ticket_id} → {new_id}")
        elif _is_permission_error(e):
            _print_permission_error(ticket_id)
            raise RuntimeError(
                "GitHub token lacks required permissions. See instructions above."
            ) from e
        else:
            raise


def _create_new_ticket(
    backend, ticket, ticket_id: str, integration_name: str, sync_state, ticket_map: dict
) -> None:
    """Create a new ticket in the external system."""
    try:
        external_ticket = backend.create_ticket(_backend_ticket_payload(ticket, ticket_id))
        external_id = (
            external_ticket.id if hasattr(external_ticket, "id") else str(external_ticket.get("id"))
        )
    except Exception as e:
        if _is_permission_error(e):
            _print_permission_error(ticket_id)
            raise RuntimeError(
                "GitHub token lacks required permissions. See instructions above."
            ) from e
        else:
            raise

    ticket_map[ticket_id] = external_id
    _record_backend_ref(ticket, integration_name, external_ticket, external_id)
    console.print(f"  ✓ Created: {ticket_id} → {external_id}")


def _record_backend_ref(
    ticket: dict, integration_name: str, external_ticket, external_id: str
) -> None:
    """Store backend-scoped references so OneDev IDs are never mistaken for GitHub IDs."""
    url = external_ticket.url if hasattr(external_ticket, "url") else external_ticket.get("url")
    key = external_ticket.key if hasattr(external_ticket, "key") else external_ticket.get("key")
    sync = ticket.setdefault("sync", {})
    sync[integration_name] = {
        key: value
        for key, value in {"id": str(external_id), "url": url, "key": key}.items()
        if value
    }
    if not ticket.get("external_id"):
        ticket["external_id"] = str(external_id)
        ticket["backend"] = integration_name


def _is_permission_error(e: Exception) -> bool:
    """Check if exception is a permission-related error."""
    err_str = str(e).lower()
    return (
        "403" in str(e)
        or "Forbidden" in str(e)
        or "not accessible by personal access token" in err_str
    )


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


def _load_sprint_and_backlog(store, v1_source_file, v1_data) -> tuple[dict, dict]:
    """Load sprint and backlog data from appropriate source."""
    if v1_source_file and v1_data:
        sprint = v1_data.get("sprint", {"tickets": {}})
        backlog = v1_data.get("backlog", {"tickets": {}})
    else:
        sprint = store.load_sprint("current") or {"tickets": {}}
        backlog = store.load_backlog() or {"tickets": {}}
    return sprint, backlog


def _fetch_external_tickets(backend, integration_name: str) -> list | None:
    """Fetch tickets from external system. Returns None on error, empty list if no tickets."""
    try:
        external_tickets = backend.list_tickets()
        if external_tickets is None:
            console.print(f"  [dim]ℹ️ No tickets found in {integration_name}[/dim]")
            return None
        return list(external_tickets)
    except Exception as e:
        console.print(f"  ✗ Failed to fetch tickets: {e}")
        return None


def _process_external_ticket(
    ext_ticket,
    sprint: dict,
    backlog: dict,
    sync_state,
    integration_name: str,
    dry_run: bool,
    imported_count: int,
    updated_count: int,
    publish_to: list[str] | None = None,
) -> tuple[int, int]:
    """Process a single external ticket. Returns updated (imported_count, updated_count)."""
    ext_data = _extract_ticket_data(ext_ticket)
    planfile_id = sync_state.get_local_id(ext_data["id"])

    if dry_run:
        _print_dry_run_action(planfile_id, ext_data)
        return imported_count, updated_count

    try:
        if planfile_id:
            return imported_count, _update_local_ticket(
                sprint, backlog, planfile_id, ext_data, updated_count, integration_name, publish_to
            )
        else:
            return _import_new_ticket(
                backlog, ext_data, integration_name, sync_state, imported_count, publish_to
            ), updated_count
    except Exception as e:
        console.print(f"  ✗ Failed to import {ext_data['id']}: {e}")
        return imported_count, updated_count


def sync_from_external(
    backend,
    store,
    dry_run: bool,
    integration_name: str,
    v1_source_file=None,
    v1_data=None,
    publish_to: list[str] | None = None,
) -> None:
    """Sync tickets from external system to planfile."""
    sync_state = SyncState(Path(store.base_dir), integration_name)
    imported_count = 0
    updated_count = 0

    sprint, backlog = _load_sprint_and_backlog(store, v1_source_file, v1_data)
    external_tickets = _fetch_external_tickets(backend, integration_name)

    if external_tickets is None:
        return
    if not external_tickets:
        console.print(f"  [dim]ℹ️ No tickets to import from {integration_name}[/dim]")
        return

    for ext_ticket in external_tickets:
        imported_count, updated_count = _process_external_ticket(
            ext_ticket,
            sprint,
            backlog,
            sync_state,
            integration_name,
            dry_run,
            imported_count,
            updated_count,
            publish_to,
        )

    if not dry_run and (imported_count > 0 or updated_count > 0):
        _save_import_results(
            store, v1_source_file, v1_data, sprint, backlog, imported_count, updated_count
        )


def _extract_ticket_data(ext_ticket) -> dict:
    """Extract standardized ticket data from external ticket (dict or Pydantic model)."""
    if hasattr(ext_ticket, "id"):
        return {
            "id": str(ext_ticket.id),
            "name": ext_ticket.name
            if hasattr(ext_ticket, "name") and ext_ticket.name
            else (ext_ticket.title if hasattr(ext_ticket, "title") else "No title"),
            "status": ext_ticket.status if hasattr(ext_ticket, "status") else "open",
            "assignee": ext_ticket.assignee if hasattr(ext_ticket, "assignee") else None,
            "labels": ext_ticket.labels if hasattr(ext_ticket, "labels") else [],
            "description": ext_ticket.description if hasattr(ext_ticket, "description") else "",
            "url": ext_ticket.url if hasattr(ext_ticket, "url") else None,
            "key": ext_ticket.key if hasattr(ext_ticket, "key") else None,
            "metadata": ext_ticket.metadata if hasattr(ext_ticket, "metadata") else {},
        }
    else:
        return {
            "id": str(ext_ticket.get("id", "")),
            "name": ext_ticket.get("name") or ext_ticket.get("title", "No title"),
            "status": ext_ticket.get("status", "open"),
            "assignee": ext_ticket.get("assignee"),
            "labels": ext_ticket.get("labels", []),
            "description": ext_ticket.get("description", ""),
            "url": ext_ticket.get("url"),
            "key": ext_ticket.get("key"),
            "metadata": ext_ticket.get("metadata", {}),
        }


def _print_dry_run_action(planfile_id: str | None, ext_data: dict) -> None:
    """Print dry-run action for a ticket."""
    if planfile_id:
        console.print(f"  Would update: {planfile_id} from {ext_data['id']}")
    else:
        console.print(f"  Would import: {ext_data.get('name') or ext_data.get('title')}")


def _integration_routes(integration_name: str, publish_to: list[str] | None) -> list[str]:
    return list(dict.fromkeys([integration_name, *(publish_to or [])]))


def _update_local_ticket(
    sprint: dict,
    backlog: dict,
    planfile_id: str,
    ext_data: dict,
    updated_count: int,
    integration_name: str,
    publish_to: list[str] | None,
) -> int:
    """Update an existing local ticket from external data."""
    backend_ref = {
        key: value
        for key, value in {
            "id": ext_data["id"],
            "url": ext_data.get("url"),
            "key": ext_data.get("key"),
        }.items()
        if value
    }
    update_fields = {
        "name": ext_data.get("name") or ext_data.get("title"),
        "description": ext_data.get("description", ""),
        "status": ext_data["status"],
        "assignee": ext_data["assignee"],
        "labels": ext_data["labels"],
        "integration": _integration_routes(integration_name, publish_to),
        "metadata": ext_data.get("metadata") or {},
    }

    if planfile_id in sprint.get("tickets", {}):
        ticket = sprint["tickets"][planfile_id]
    elif planfile_id in backlog.get("tickets", {}):
        ticket = backlog["tickets"][planfile_id]
    else:
        return updated_count

    ticket.update(update_fields)
    ticket.setdefault("sync", {})[integration_name] = backend_ref

    console.print(f"  ✓ Updated: {planfile_id} from {ext_data['id']}")
    return updated_count + 1


def _import_new_ticket(
    backlog: dict,
    ext_data: dict,
    integration_name: str,
    sync_state,
    imported_count: int,
    publish_to: list[str] | None = None,
) -> int:
    """Import a new ticket from external system."""
    new_id = f"{integration_name.upper()}-{ext_data['id']}"

    ticket_data = {
        "name": ext_data.get("name") or ext_data.get("title"),
        "description": ext_data["description"],
        "status": ext_data["status"],
        "assignee": ext_data["assignee"],
        "labels": ext_data["labels"],
        "external_id": ext_data["id"],
        "backend": integration_name,
        "integration": _integration_routes(integration_name, publish_to),
        "metadata": ext_data.get("metadata") or {},
        "sync": {
            integration_name: {
                key: value
                for key, value in {
                    "id": ext_data["id"],
                    "url": ext_data.get("url"),
                    "key": ext_data.get("key"),
                }.items()
                if value
            }
        },
    }

    backlog["tickets"][new_id] = ticket_data
    sync_state.save_sync({new_id: ext_data["id"]})

    console.print(f"  ✓ Imported: {new_id} ← {ext_data['id']}")
    return imported_count + 1


def _save_import_results(
    store, v1_source_file, v1_data, sprint, backlog, imported_count, updated_count
) -> None:
    """Save import results to appropriate storage."""
    from planfile.sync.utils import save_v1_format

    if v1_source_file and v1_data:
        if "sprint" in v1_data:
            v1_data["sprint"] = sprint
        if "backlog" in v1_data:
            v1_data["backlog"] = backlog
        save_v1_format(v1_source_file, v1_data)
        console.print(
            f"\n💾 Saved {imported_count} imported, {updated_count} updated to {Path(v1_source_file).name}"
        )
    else:
        store.save_sprint("current", sprint)
        store.save_backlog(backlog)
        console.print(
            f"\n📥 Imported {imported_count} new tickets, updated {updated_count} existing"
        )
