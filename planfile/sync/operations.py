"""Sync operations - bidirectional ticket synchronization with external systems."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rich.console import Console

from planfile.sync.state import SyncState, normalize_repository

console = Console()


def _backend_repository(backend) -> str | None:
    """Return the configured repository without persisting credentials."""
    config = getattr(backend, "config", {})
    value = config.get("repo") if isinstance(config, dict) else None
    if value is None:
        repository = getattr(backend, "repo", None)
        value = getattr(repository, "full_name", None)
    return normalize_repository(value) if value else None


def _validate_ticket_binding(ticket: dict, integration_name: str, backend) -> None:
    """Reject an embedded reference that belongs to another repository."""
    repository = _backend_repository(backend)
    if not repository:
        return
    reference = (ticket.get("sync") or {}).get(integration_name) or {}
    if not isinstance(reference, dict):
        return
    candidates = [reference.get("repository"), reference.get("repo")]
    url = str(reference.get("url") or "")
    if "/issues/" in url:
        candidates.append(url.split("github.com/", 1)[-1].split("/issues/", 1)[0])
    key = str(reference.get("key") or "")
    if "#" in key:
        candidates.append(key.split("#", 1)[0])
    for candidate in candidates:
        if candidate:
            normalized = normalize_repository(str(candidate))
            if normalized != repository:
                raise ValueError(
                    f"ticket {ticket.get('id') or '<unknown>'} maps to {normalized}, "
                    f"backend targets {repository}"
                )


def sync_to_external(
    backend, tickets, dry_run: bool, store, integration_name: str, v1_source_file=None, v1_data=None
) -> Any:
    """Use the canonical fail-closed batcher for legacy callers as well."""
    # Import lazily because outbound.py reuses the helper functions defined in
    # this module. This keeps the public legacy entry point compatible without
    # introducing an import cycle at module load time.
    from planfile.sync.outbound import sync_to_external as sync_outbound

    return sync_outbound(
        backend,
        tickets,
        dry_run,
        store,
        integration_name,
        v1_source_file,
        v1_data,
    )


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


def _backend_ticket_payload(
    ticket: dict,
    ticket_id: str,
    repository: str | None = None,
    store_identity: str | None = None,
) -> dict:
    payload = dict(ticket)
    metadata = dict(payload.get("metadata") or {})
    if repository:
        metadata.setdefault("repository", repository)
        namespace = f"{repository}:{store_identity}" if store_identity else repository
        metadata.setdefault("planfile_id", f"{namespace}:{ticket_id}")
    else:
        metadata.setdefault("planfile_id", ticket_id)
    payload["metadata"] = metadata
    return payload


def _update_existing_ticket(
    backend, ticket, ticket_id: str, external_id: str, integration_name: str, sync_state
) -> str:
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
        # A mapping may have been recovered from the backend state file after
        # an interrupted create. Keep the physical ticket record equally
        # authoritative so ``ticket show`` and later retries expose the same
        # backend-scoped identity. The update API does not return a TicketRef,
        # therefore persist the stable ID and preserve richer fields already
        # present on the local record.
        _record_backend_ref(
            ticket,
            integration_name,
            {"id": str(external_id)},
            external_id,
        )
        console.print(f"  ✓ Updated: {ticket_id} → {external_id}")
    except Exception as e:
        if _is_rate_limit_error(e):
            _print_rate_limit_error(ticket_id, e)
            # Keep status and retry headers available to the outbound scheduler.
            raise
        elif "404" in str(e) or "Not Found" in str(e):
            console.print(f"  ⚠️  Issue not found, creating new: {external_id}")
            external_ticket = backend.create_ticket(
                _backend_ticket_payload(
                    ticket,
                    ticket_id,
                    _backend_repository(backend),
                    getattr(sync_state, "store_identity", None),
                )
            )
            new_id = (
                external_ticket.id
                if hasattr(external_ticket, "id")
                else str(external_ticket.get("id"))
            )
            sync_state.save_sync({ticket_id: new_id})
            _record_backend_ref(ticket, integration_name, external_ticket, new_id)
            console.print(f"  ✓ Created: {ticket_id} → {new_id}")
            return "created"
        elif _is_permission_error(e):
            _print_permission_error(ticket_id)
            raise RuntimeError(
                "GitHub token lacks required permissions. See instructions above."
            ) from e
        else:
            raise
    return "updated"


def _create_new_ticket(
    backend, ticket, ticket_id: str, integration_name: str, sync_state, ticket_map: dict
):
    """Create a new ticket in the external system.

    Returns ``(external_id, external_ticket)``. Does not record the reference
    on *ticket* or announce success — the caller verifies the readback first,
    so an id this call could not actually vouch for (e.g. a lost-response
    retry) is never persisted before that check runs.
    """
    try:
        external_ticket = backend.create_ticket(
            _backend_ticket_payload(
                ticket,
                ticket_id,
                _backend_repository(backend),
                getattr(sync_state, "store_identity", None),
            )
        )
        external_id = (
            external_ticket.id if hasattr(external_ticket, "id") else str(external_ticket.get("id"))
        )
    except Exception as e:
        if _is_rate_limit_error(e):
            _print_rate_limit_error(ticket_id, e)
            raise
        elif _is_permission_error(e):
            _print_permission_error(ticket_id)
            raise RuntimeError(
                "GitHub token lacks required permissions. See instructions above."
            ) from e
        else:
            raise

    ticket_map[ticket_id] = external_id
    return external_id, external_ticket


def _record_backend_ref(
    ticket: dict, integration_name: str, external_ticket, external_id: str
) -> None:
    """Store backend-scoped references so OneDev IDs are never mistaken for GitHub IDs."""
    url = external_ticket.url if hasattr(external_ticket, "url") else external_ticket.get("url")
    key = external_ticket.key if hasattr(external_ticket, "key") else external_ticket.get("key")
    sync = ticket.setdefault("sync", {})
    existing = sync.get(integration_name)
    reference = dict(existing) if isinstance(existing, dict) else {}
    reference.update(
        {
            key: value
            for key, value in {"id": str(external_id), "url": url, "key": key}.items()
            if value
        }
    )
    if url and "github.com/" in str(url):
        reference["repository"] = str(url).split("github.com/", 1)[1].split("/issues/", 1)[0]
    sync[integration_name] = reference
    if not ticket.get("external_id"):
        ticket["external_id"] = str(external_id)
        ticket["backend"] = integration_name


def _is_rate_limit_error(e: Exception) -> bool:
    """Distinguish exhausted provider quotas from an ordinary access denial."""
    status = getattr(e, "status", None)
    headers = _error_headers(e)
    if status == 429:
        return True
    if status == 403 and (
        str(headers.get("x-ratelimit-remaining")) == "0" or "retry-after" in headers
    ):
        return True
    err_str = str(e).lower()
    return any(
        marker in err_str
        for marker in ("rate limit", "ratelimit", "secondary limit", "abuse detection")
    )


def _error_headers(e: Exception) -> dict:
    headers = getattr(e, "headers", None)
    if not isinstance(headers, dict):
        return {}
    return {str(key).lower(): value for key, value in headers.items()}


def _is_permission_error(e: Exception) -> bool:
    """Check if exception is a permission-related error."""
    if _is_rate_limit_error(e):
        return False
    err_str = str(e).lower()
    return (
        "403" in str(e)
        or "Forbidden" in str(e)
        or "not accessible by personal access token" in err_str
    )


def _print_rate_limit_error(ticket_id: str, e: Exception) -> None:
    """Print bounded retry metadata without response bodies or credentials."""
    console.print(f"[red]❌ GitHub API rate limit exceeded for {ticket_id}[/red]")
    headers = _error_headers(e)
    for key, label in (("retry-after", "Retry-After (seconds)"),
                       ("x-ratelimit-reset", "X-RateLimit-Reset (Unix seconds)")):
        value = str(headers.get(key, ""))
        if re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,3})?", value):
            console.print(f"  {label}: {value}")
    console.print("[yellow]Wait for the provider's retry window, then retry the same tickets.[/yellow]")
    console.print("[yellow]Rate limiting does not establish missing permissions; keep the existing account and token.[/yellow]")


def _print_permission_error(ticket_id: str) -> None:
    """Print permission error instructions."""
    console.print(f"[red]❌ GitHub permission denied for {ticket_id}[/red]")
    console.print("[yellow]Verify the configured account and its access to Issues in this repository.[/yellow]")
    console.print("[yellow]Correct the missing repository permission before retrying the same tickets.[/yellow]")


def _save_sync_results(
    store,
    v1_source_file,
    v1_data,
    *,
    tickets: list[tuple[str, dict]] | None = None,
) -> None:
    """Save sync results to appropriate storage."""
    from planfile.sync.utils import save_v1_format

    if v1_source_file and v1_data:
        save_v1_format(v1_source_file, v1_data)
        console.print(f"  💾 Saved changes to {Path(v1_source_file).name}")
    else:
        if tickets and hasattr(store, "_all_sprint_ids"):
            # Outbound mutation can touch a custom or archived sprint. Save
            # only those physical sections instead of silently dropping the
            # updated backend reference by persisting current/backlog alone.
            changed_ids = {str(ticket_id): ticket for ticket_id, ticket in tickets}
            for sprint_id in store._all_sprint_ids():
                section = store.load_sprint(sprint_id)
                physical_tickets = section.get("tickets") or {}
                changed = False
                for ticket_id, ticket in changed_ids.items():
                    if ticket_id in physical_tickets:
                        physical_tickets[ticket_id] = ticket
                        changed = True
                if changed:
                    section["tickets"] = physical_tickets
                    store.save_sprint(sprint_id, section)
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


def _load_sync_sections(store, v1_source_file, v1_data) -> dict[str, dict]:
    """Load every writable Planfile sprint for inbound reconciliation.

    History is intentionally included for mapped terminal tickets, while
    imports still default to the backlog. Keeping the section identity lets a
    custom sprint retain ownership of a ticket instead of silently moving it.
    """
    if v1_source_file and v1_data:
        return {
            name: value
            for name in ("sprint", "backlog")
            if isinstance(value := v1_data.get(name), dict)
        }
    sections: dict[str, dict] = {}
    sprint_ids = []
    if hasattr(store, "_all_sprint_ids"):
        sprint_ids = list(store._all_sprint_ids())
    if not sprint_ids:
        sprint_ids = ["current", "backlog"]
    for sprint_id in sprint_ids:
        section = store.load_sprint(sprint_id)
        if isinstance(section, dict):
            sections[str(sprint_id)] = section
    return sections


def _find_local_ticket(
    sections: dict[str, dict],
    remote_id: str,
    sync_state,
    integration_name: str,
) -> tuple[str | None, str | None, dict | None]:
    """Find an existing mapping even when the state ledger predates a repair."""
    planfile_id = sync_state.get_local_id(remote_id)
    if planfile_id:
        for sprint_id, section in sections.items():
            ticket = (section.get("tickets") or {}).get(planfile_id)
            if isinstance(ticket, dict):
                return sprint_id, planfile_id, ticket
    matches: list[tuple[str, str, dict]] = []
    for sprint_id, section in sections.items():
        for local_id, ticket in (section.get("tickets") or {}).items():
            if not isinstance(ticket, dict):
                continue
            reference = (ticket.get("sync") or {}).get(integration_name) or {}
            if isinstance(reference, dict) and str(reference.get("id")) == str(remote_id):
                matches.append((str(sprint_id), str(local_id), ticket))
    if len(matches) > 1:
        raise ValueError(f"ambiguous local mapping for remote ticket {remote_id}")
    return matches[0] if matches else (None, None, None)


def _fetch_external_tickets(
    backend,
    integration_name: str,
    labels: list[str] | None = None,
) -> list | None:
    """Fetch tickets from external system. Returns None on error, empty list if no tickets."""
    try:
        kwargs = {"labels": labels} if labels else {}
        external_tickets = backend.list_tickets(**kwargs)
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
    sections: dict[str, dict] | None = None,
    ticket_ids: set[str] | None = None,
    import_target: dict | None = None,
) -> tuple[int, int]:
    """Process a single external ticket. Returns updated (imported_count, updated_count)."""
    ext_data = _extract_ticket_data(ext_ticket)
    if sections is None:
        sections = {"current": sprint, "backlog": backlog}
    sprint_name, planfile_id, local_ticket = _find_local_ticket(
        sections, ext_data["id"], sync_state, integration_name
    )
    if local_ticket is None:
        planfile_id = None
    if ticket_ids and planfile_id not in ticket_ids:
        return imported_count, updated_count

    if dry_run:
        _print_dry_run_action(planfile_id, ext_data)
        return imported_count, updated_count

    try:
        if planfile_id:
            target = sections.get(sprint_name or "")
            if target is None:
                return imported_count, updated_count
            result = _update_local_ticket(
                target, {}, planfile_id, ext_data, updated_count, integration_name, publish_to
            )
            if not dry_run:
                # Backfill the durable reverse mapping when an old ticket only
                # carried its embedded sync reference.
                sync_state.save_sync({planfile_id: ext_data["id"]})
            return imported_count, result
        else:
            return _import_new_ticket(
                import_target or backlog,
                ext_data,
                integration_name,
                sync_state,
                imported_count,
                publish_to,
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
    ticket_ids: list[str] | None = None,
    sprint_ids: list[str] | None = None,
    remote_labels: list[str] | None = None,
) -> None:
    """Sync tickets from external system to planfile."""
    sync_state = SyncState(
        Path(store.base_dir), integration_name, repository=_backend_repository(backend)
    )
    imported_count = 0
    updated_count = 0

    sprint, backlog = _load_sprint_and_backlog(store, v1_source_file, v1_data)
    sections = _load_sync_sections(store, v1_source_file, v1_data)
    # Reuse the snapshots returned by the compatibility loader so imports into
    # the backlog are the same objects that are persisted below.
    sections["current"] = sprint
    sections["backlog"] = backlog
    requested_sprints = list(
        dict.fromkeys(str(value).strip() for value in (sprint_ids or []) if str(value).strip())
    )
    import_target = backlog
    lookup_sections = sections
    if requested_sprints:
        # An explicit sprint scope is also the destination for newly imported
        # tickets. Unknown IDs fail closed rather than silently falling back to
        # the global backlog.
        target_id = next((value for value in requested_sprints if value in sections), None)
        if target_id is None:
            return
        import_target = sections[target_id]
        lookup_sections = {target_id: import_target}
    external_tickets = _fetch_external_tickets(backend, integration_name, remote_labels)

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
            lookup_sections,
            {str(value).strip() for value in (ticket_ids or []) if str(value).strip()},
            import_target,
        )

    if not dry_run and (imported_count > 0 or updated_count > 0):
        _save_import_results(
            store,
            v1_source_file,
            v1_data,
            sprint,
            backlog,
            imported_count,
            updated_count,
            sections=sections,
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
        "id": planfile_id,
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
        default_sprint = str(sprint.get("id") or "current")
    elif planfile_id in backlog.get("tickets", {}):
        ticket = backlog["tickets"][planfile_id]
        default_sprint = str(backlog.get("id") or "backlog")
    else:
        return updated_count

    ticket.update(update_fields)
    ticket.setdefault("sprint", default_sprint)
    if ext_data.get("url") and "github.com/" in str(ext_data["url"]):
        backend_ref["repository"] = str(ext_data["url"]).split("github.com/", 1)[1].split(
            "/issues/", 1
        )[0]
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
        # Legacy importers omitted this field, making the record invisible to
        # the typed store and ``ticket list/show``. Keep the generated local ID
        # as the canonical key in every physical sprint format.
        "id": new_id,
        "name": ext_data.get("name") or ext_data.get("title"),
        "description": ext_data["description"],
        "status": ext_data["status"],
        "sprint": "backlog",
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
    store,
    v1_source_file,
    v1_data,
    sprint,
    backlog,
    imported_count,
    updated_count,
    *,
    sections: dict[str, dict] | None = None,
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
        if sections:
            for sprint_id, section in sections.items():
                store.save_sprint(sprint_id, section)
        else:
            store.save_sprint("current", sprint)
            store.save_backlog(backlog)
        console.print(
            f"\n📥 Imported {imported_count} new tickets, updated {updated_count} existing"
        )
