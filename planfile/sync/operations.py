"""Sync operations - bidirectional ticket synchronization with external systems."""

from __future__ import annotations

import inspect
import logging
import os
import re
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from planfile.sync.deadline import (
    SyncDeadlineExceededError,
    bind_backend_deadline,
    resolve_inbound_deadline,
)
from planfile.sync.priority import normalize_inbound_priority
from planfile.sync.state import SyncState, SyncStateRepositoryMismatch, normalize_repository

logger = logging.getLogger(__name__)
console = Console()


def _backend_repository(backend) -> str | None:
    """Return the configured repository without persisting credentials."""
    verified = getattr(backend, "_verified_repository", None)
    if isinstance(verified, str) and verified:
        return normalize_repository(verified)
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
    aliases = getattr(backend, "_verified_repository_aliases", ())
    if not isinstance(aliases, (tuple, list, set)):
        aliases = ()
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
            if normalized != repository and normalized not in aliases:
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
    body = ticket.get("description", "") or ticket.get("body", "")
    if getattr(backend, "_managed_description_projection", False) is True:
        body = ticket.get("description") if "description" in ticket else ticket.get("body")
    try:
        backend.update_ticket(
            external_id,
            name=ticket.get("name") or ticket.get("title"),
            body=body,
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
            raise RuntimeError("sync_mapped_ticket_unavailable") from e
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


def _reject_github_pull_request_url(integration_name: str, url: Any) -> None:
    """Refuse to persist a GitHub Pull Request URL as a ticket mapping."""
    if integration_name != "github" or not url:
        return
    text = str(url).strip().lower()
    if "github.com/" in text and "/pull/" in text:
        raise ValueError("sync_github_pull_request_mapping_forbidden")


def _record_backend_ref(
    ticket: dict, integration_name: str, external_ticket, external_id: str
) -> None:
    """Store backend-scoped references so OneDev IDs are never mistaken for GitHub IDs."""
    url = external_ticket.url if hasattr(external_ticket, "url") else external_ticket.get("url")
    _reject_github_pull_request_url(integration_name, url)
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


def _ordered_sprints_for_ticket(
    sections: dict[str, dict], ticket_id: str, store: Any = None
) -> list[str]:
    """Return section sprint IDs in the exact lookup order used by store.update_ticket."""
    lookup = getattr(store, "_ticket_lookup_sprints", None) if store is not None else None
    if callable(lookup):
        ordered: list[str] = []
        seen: set[str] = set()
        for sprint_id in lookup(ticket_id):
            key = str(sprint_id)
            if key in sections and key not in seen:
                ordered.append(key)
                seen.add(key)
        for sprint_id in sections:
            if sprint_id not in seen:
                ordered.append(sprint_id)
        return ordered
    return list(sections.keys())


def _find_local_ticket(
    sections: dict[str, dict],
    remote_id: str,
    sync_state,
    integration_name: str,
    ext_data: dict | None = None,
    store: Any = None,
    known_ticket_map: dict[str, str] | None = None,
) -> tuple[str | None, str | None, dict | None]:
    """Find an existing mapping even when the state ledger predates a repair."""
    if known_ticket_map is not None:
        id_matches = [
            str(local_id)
            for local_id, mapped_id in known_ticket_map.items()
            if str(mapped_id) == str(remote_id)
        ]
        if len(id_matches) > 1:
            raise ValueError(f"ambiguous sync mapping for remote ticket {remote_id}")
        planfile_id = id_matches[0] if id_matches else None
    else:
        planfile_id = sync_state.get_local_id(remote_id)
    if planfile_id:
        for sprint_id in _ordered_sprints_for_ticket(sections, planfile_id, store):
            section = sections[sprint_id]
            ticket = (section.get("tickets") or {}).get(planfile_id)
            if isinstance(ticket, dict):
                return sprint_id, planfile_id, ticket

    # Check deduplication markers from external ticket
    if ext_data:
        candidate_keys = []
        desc = ext_data.get("description") or ""
        marker_match = re.search(r"<!--\s*planfile:deduplication-key=([^>]+?)\s*-->", desc)
        if marker_match:
            candidate_keys.append(marker_match.group(1).strip())
        meta = ext_data.get("metadata") or {}
        if isinstance(meta, dict):
            for k in ("planfile_id", "deduplication_key", "dedupe_key", "fingerprint"):
                v = meta.get(k)
                if v and str(v).strip():
                    val = str(v).strip()
                    if ":" in val:
                        val = val.split(":")[-1].strip()
                    candidate_keys.append(val)
        for cand in candidate_keys:
            for sprint_id in _ordered_sprints_for_ticket(sections, cand, store):
                section = sections[sprint_id]
                ticket = (section.get("tickets") or {}).get(cand)
                if isinstance(ticket, dict):
                    return sprint_id, cand, ticket
                for lid, t in (section.get("tickets") or {}).items():
                    if isinstance(t, dict):
                        labels = t.get("labels") or []
                        if f"dedupe:{cand}" in labels:
                            return sprint_id, str(lid), t

    synthetic_id = f"{integration_name.upper()}-{remote_id}"
    matches: list[tuple[str, str, dict]] = []
    for sprint_id, section in sections.items():
        for local_id, ticket in (section.get("tickets") or {}).items():
            if not isinstance(ticket, dict):
                continue
            reference = (ticket.get("sync") or {}).get(integration_name) or {}
            if isinstance(reference, dict) and str(reference.get("id")) == str(remote_id):
                matches.append((str(sprint_id), str(local_id), ticket))
            elif str(ticket.get("external_id") or "") == str(remote_id) and str(ticket.get("backend") or "") == integration_name:
                matches.append((str(sprint_id), str(local_id), ticket))
            elif str(local_id) == synthetic_id:
                matches.append((str(sprint_id), str(local_id), ticket))
    if len(matches) > 1:
        unique_local_ids = {m[1] for m in matches}
        if len(unique_local_ids) == 1:
            only_id = next(iter(unique_local_ids))
            preferred_order = (
                _ordered_sprints_for_ticket(sections, only_id, store)
                if store is not None
                else ["current", "backlog"]
            )
            for preferred in preferred_order:
                for m in matches:
                    if m[0] == preferred:
                        return m
            return matches[0]
        preferred_matches = [m for m in matches if m[0] in ("current", "backlog")]
        if len(preferred_matches) == 1:
            return preferred_matches[0]
        raise ValueError(f"ambiguous local mapping for remote ticket {remote_id}: {sorted(unique_local_ids)}")
    return matches[0] if matches else (None, None, None)


_INCREMENTAL_SINCE_OVERLAP_SECONDS = 60
_FULL_SYNC_ENV_VAR = "PLANFILE_SYNC_FULL"


def _supports_since_filter(backend) -> bool:
    """Return True when the backend explicitly declares an optional ``since`` parameter."""
    # Check both instance and class methods because bind_backend_deadline wraps
    # instance ``list_tickets`` without preserving inspect.signature metadata.
    candidates: list[Any] = []
    if callable(getattr(backend, "_list_tickets", None)):
        candidates.extend((getattr(backend, "_list_tickets", None), getattr(type(backend), "_list_tickets", None)))
    else:
        candidates.extend((getattr(backend, "list_tickets", None), getattr(type(backend), "list_tickets", None)))
    for target in candidates:
        if not callable(target):
            continue
        try:
            sig = inspect.signature(target)
        except (TypeError, ValueError):
            continue
        if "since" in sig.parameters:
            return True
    return False


def _resolve_incremental_since(
    sync_state,
    integration_name: str,
    *,
    selected_remote_ids: set[str] | None,
    remote_labels: list[str] | None,
    requested_sprints: list[str],
) -> datetime | None:
    """Resolve an incremental ``since`` watermark for unscoped GitHub inbound syncs."""
    if (
        integration_name != "github"
        or selected_remote_ids is not None
        or remote_labels
        or requested_sprints
    ):
        return None
    if os.environ.get(_FULL_SYNC_ENV_VAR, "").strip().lower() in {"1", "true", "yes"}:
        return None
    try:
        raw_state = sync_state.get_last_sync()
    except Exception:
        return None
    if not isinstance(raw_state, dict):
        return None
    raw_cursor = raw_state.get("inbound_cursor_at")
    if not isinstance(raw_cursor, str) or not raw_cursor.strip():
        return None
    try:
        cursor = datetime.fromisoformat(raw_cursor.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if cursor.tzinfo is None:
        cursor = cursor.replace(tzinfo=timezone.utc)
    else:
        cursor = cursor.astimezone(timezone.utc)
    return cursor - timedelta(seconds=_INCREMENTAL_SINCE_OVERLAP_SECONDS)


def _freeze_observed_updated_at(sections: dict[str, dict], store: Any) -> dict[str, str | None]:
    """Capture evidence-projected updated_at revisions in canonical store lookup order."""
    projector = getattr(store, "_project_ticket_evidence", None)
    observed: dict[str, str | None] = {}
    seen_ids: set[str] = set()
    for section in sections.values():
        if not isinstance(section, dict):
            continue
        for tid in section.get("tickets") or {}:
            seen_ids.add(str(tid))
    for tid in seen_ids:
        raw_ticket = None
        for sprint_id in _ordered_sprints_for_ticket(sections, tid, store):
            cand = (sections[sprint_id].get("tickets") or {}).get(tid)
            if isinstance(cand, dict):
                raw_ticket = cand
                break
        if raw_ticket is None:
            continue
        projected = raw_ticket
        if callable(projector):
            raw_with_id = raw_ticket if raw_ticket.get("id") else {**raw_ticket, "id": tid}
            try:
                projected = projector(raw_with_id)
            except ValueError:
                projected = raw_ticket
        if isinstance(projected, dict):
            observed[tid] = projected.get("updated_at")
        else:
            observed[tid] = raw_ticket.get("updated_at")
    return observed


def _snapshot_ticket_map(sync_state: Any) -> dict[str, str] | None:
    """Load ticket_map once into memory to avoid O(N) YAML reads during inbound sync."""
    getter = getattr(sync_state, "get_last_sync", None)
    if not callable(getter):
        return None
    try:
        raw_state = getter()
    except Exception:
        return None
    if not isinstance(raw_state, dict):
        return None
    raw_map = raw_state.get("ticket_map")
    if raw_map is None:
        return {}
    if not isinstance(raw_map, dict):
        return None
    return {
        str(k): str(v)
        for k, v in raw_map.items()
        if str(k).strip() and str(v).strip()
    }


def _save_sync_state_metadata(
    sync_state: Any,
    *,
    inbound_cursor_at: str,
    quarantined_inbound_tickets: list[dict[str, str]] | None = None,
) -> None:
    """Persist cursor/quarantine metadata while respecting minimal sync_state stubs."""
    save_fn = getattr(sync_state, "save_sync", None)
    if not callable(save_fn):
        return
    kwargs: dict[str, Any] = {}
    try:
        params = inspect.signature(save_fn).parameters
    except (TypeError, ValueError):
        params = {}
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if has_var_kw or "inbound_cursor_at" in params:
        kwargs["inbound_cursor_at"] = inbound_cursor_at
    if quarantined_inbound_tickets is not None and (
        has_var_kw or "quarantined_inbound_tickets" in params
    ):
        kwargs["quarantined_inbound_tickets"] = quarantined_inbound_tickets
    save_fn({}, **kwargs)


def _is_isolatable_ticket_conflict(exc: Exception) -> bool:
    """Return True when an inbound per-ticket conflict can be safely quarantined."""
    if type(exc).__name__ == "TicketUpdatedAtConflictError":
        return True
    if isinstance(exc, ValueError):
        msg = str(exc)
        return any(
            marker in msg
            for marker in (
                "inbound_terminal_transition_requires_execution_reconciliation",
                "stale_ticket_snapshot",
                "inbound_ticket_disappeared",
                "ticket_already_exists",
                "inbound_priority_invalid",
                "inbound_priority_conflict",
                "ambiguous sync mapping",
                "evidence_ticket_id_invalid",
            )
        )
    return False


def _fetch_external_tickets(
    backend,
    integration_name: str,
    labels: list[str] | None = None,
    selected_remote_ids: set[str] | None = None,
    since: datetime | None = None,
) -> list | None:
    """Fetch tickets; preserve provider failures for caller retry and cooldown."""
    try:
        kwargs: dict[str, Any] = {"labels": labels} if labels else {}
        selected_reader = getattr(backend, "list_selected_tickets", None)
        if (integration_name == "github" and selected_remote_ids is not None
                and callable(selected_reader)):
            external_tickets = selected_reader(selected_remote_ids, **kwargs)
        else:
            if since is not None and _supports_since_filter(backend):
                kwargs["since"] = since
            external_tickets = backend.list_tickets(**kwargs)
        if external_tickets is None:
            console.print(f"  [dim]ℹ️ No tickets found in {integration_name}[/dim]")
            return None
        return list(external_tickets)
    except SyncDeadlineExceededError:
        raise
    except Exception as error:
        # Provider diagnostics may contain credentials. Keep a bounded message
        # and the cause so the caller can still observe retry/cooldown hints.
        raise RuntimeError("sync_inbound_fetch_failed") from error


def _ticket_trace_id(ext_ticket: Any) -> str:
    """Return a concise non-empty identifier for inbound deadline diagnostics."""
    for attr in ("id", "key", "number", "external_id"):
        value = getattr(ext_ticket, attr, None)
        if value is not None and str(value).strip():
            return str(value).strip()
    return repr(ext_ticket)


def _resolve_selected_remote_ids(
    ticket_ids: set[str] | list[str] | None,
    sections: dict[str, dict] | None,
    sync_state,
    integration_name: str,
    *,
    strict_local: bool = False,
) -> set[str] | None:
    """Resolve filters, optionally giving local identities precedence over aliases."""
    if not ticket_ids:
        return None
    normalized = {str(value).strip() for value in ticket_ids if str(value).strip()}
    if not normalized:
        return None

    remote_ids: set[str] = set()
    for tid in normalized:
        # Explicit GitHub references always name remote issues. A bare numeric
        # selector can instead be a real local ID, mapped to a different issue.
        if strict_local and "#" in tid:
            remote_ids.add(tid)
            continue
        mapped_ids: set[str] = set()
        local_found = False

        # Look up in sync_state (local -> remote mapping)
        if sync_state is not None and hasattr(sync_state, "get_remote_id"):
            try:
                mapped_remote = sync_state.get_remote_id(tid)
                if mapped_remote:
                    mapped_ids.add(str(mapped_remote).strip())
            except Exception as exc:
                logger.debug("sync_state remote id lookup failed for ticket %s: %s", tid, exc)
                if strict_local:
                    raise

        # Look up in sections (section tickets -> sync.<integration>.id)
        if sections:
            for _sprint_id, section in sections.items():
                if not isinstance(section, dict):
                    continue
                ticket = (section.get("tickets") or {}).get(tid)
                if isinstance(ticket, dict):
                    local_found = True
                    ref = (ticket.get("sync") or {}).get(integration_name) or {}
                    if isinstance(ref, dict):
                        rid = ref.get("id")
                        if rid is not None and str(rid).strip():
                            mapped_ids.add(str(rid).strip())

        if strict_local:
            if len(mapped_ids) > 1:
                raise ValueError(f"conflicting selected remote mapping for local ticket {tid}")
            if local_found or mapped_ids:
                remote_ids.update(mapped_ids)
                continue
        clean = tid.lstrip("#")
        remote_ids.update((tid, clean))
        remote_ids.update(mapped_ids)

    return remote_ids


_DEDUP_MARKER_RE = re.compile(r"<!--\s*planfile:deduplication-key=([^>]+?)\s*-->")


def _retired_own_dedup_origin(ext_data: dict, sync_state: Any) -> str | None:
    """Return the original local ticket ID if ext_data carries this store's dedup marker.

    When a ticket originally created by this repository and Planfile store is
    later retired locally, inbound sync must not resurrect it as a duplicate
    ``GITHUB-N`` ticket. Matching requires both the canonical repository name
    and the clone-local ``store_identity`` namespace so issues originating from
    other repositories or other clones still import normally.
    """
    repository = str(getattr(sync_state, "repository", "") or "").strip().lower()
    store_identity = str(getattr(sync_state, "store_identity", "") or "").strip()
    if not repository or not store_identity:
        return None

    raw_keys: list[str] = []
    desc = ext_data.get("description") or ""
    marker_match = _DEDUP_MARKER_RE.search(desc)
    if marker_match:
        raw_keys.append(marker_match.group(1).strip())
    meta = ext_data.get("metadata") or {}
    if isinstance(meta, dict):
        for field in ("planfile_id", "deduplication_key", "dedupe_key"):
            value = meta.get(field)
            if value and str(value).strip():
                raw_keys.append(str(value).strip())

    for raw_key in raw_keys:
        parts = raw_key.split(":", 2)
        if len(parts) != 3:
            continue
        key_repo, key_store_id, key_local_id = (
            parts[0].strip().lower(),
            parts[1].strip(),
            parts[2].strip(),
        )
        if key_repo == repository and key_store_id == store_identity and key_local_id:
            return key_local_id
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
    selected_remote_ids: set[str] | None = None,
    store=None,
    observed_updated_at: dict[str, str | None] | None = None,
    known_ticket_map: dict[str, str] | None = None,
    isolate_ticket_conflicts: bool = False,
    quarantined_tickets: list[dict[str, str]] | None = None,
) -> tuple[int, int]:
    """Process a single external ticket. Returns updated (imported_count, updated_count)."""
    ext_data = _extract_ticket_data(ext_ticket)
    if sections is None:
        sections = {"current": sprint, "backlog": backlog}

    if ticket_ids:
        if selected_remote_ids is None:
            selected_remote_ids = _resolve_selected_remote_ids(
                ticket_ids, sections, sync_state, integration_name
            )
        if selected_remote_ids is not None:
            candidate_ids = {ext_data["id"], f"#{ext_data['id']}"}
            if ext_data.get("key"):
                candidate_ids.add(str(ext_data["key"]).strip())
            if not candidate_ids.intersection(selected_remote_ids):
                return imported_count, updated_count

    try:
        sprint_name, planfile_id, local_ticket = _find_local_ticket(
            sections,
            ext_data["id"],
            sync_state,
            integration_name,
            ext_data=ext_data,
            store=store,
            known_ticket_map=known_ticket_map,
        )
    except Exception as e:
        if store is not None and isolate_ticket_conflicts and _is_isolatable_ticket_conflict(e):
            console.print(
                f"  [yellow]⚠️ Quarantined {ext_data['id']} "
                f"(remote #{ext_data['id']}): {e}[/yellow]"
            )
            if quarantined_tickets is not None:
                quarantined_tickets.append(
                    {
                        "local_id": "",
                        "remote_id": str(ext_data["id"]),
                        "reason": str(e)[:200],
                    }
                )
            return imported_count, updated_count
        raise
    if local_ticket is None:
        planfile_id = None
        generated_id = f"{integration_name.upper()}-{ext_data['id']}"
        for sec_name in _ordered_sprints_for_ticket(sections, generated_id, store):
            sec = sections[sec_name]
            sec_tickets = sec.get("tickets") if isinstance(sec, dict) else None
            if isinstance(sec_tickets, dict) and isinstance(sec_tickets.get(generated_id), dict):
                sprint_name = sec_name
                planfile_id = generated_id
                local_ticket = sec_tickets[generated_id]
                break
    if ticket_ids:
        matches_local = bool(planfile_id and planfile_id in ticket_ids)
        matches_remote = bool(
            ext_data["id"] in ticket_ids
            or f"#{ext_data['id']}" in ticket_ids
            or (ext_data.get("key") and str(ext_data["key"]).strip() in ticket_ids)
        )
        if not (matches_local or matches_remote):
            return imported_count, updated_count

    try:
        if not planfile_id:
            retired_origin = _retired_own_dedup_origin(ext_data, sync_state)
            if retired_origin:
                console.print(
                    f"  [dim]⏭ Skipped retired local origin {retired_origin} "
                    f"(remote #{ext_data['id']})[/dim]"
                )
                return imported_count, updated_count
        if dry_run:
            if not planfile_id:
                normalize_inbound_priority(ext_data)
            _print_dry_run_action(planfile_id, ext_data)
            return imported_count, updated_count
        if planfile_id:
            target = sections.get(sprint_name or "")
            if target is None:
                return imported_count, updated_count
            result = _update_local_ticket(
                target, {}, planfile_id, ext_data, updated_count, integration_name, publish_to,
                store=store, observed_updated_at=observed_updated_at,
            )
            if not dry_run:
                remote_str = str(ext_data["id"])
                # Backfill the durable reverse mapping only when missing or changed.
                if known_ticket_map is None or known_ticket_map.get(planfile_id) != remote_str:
                    sync_state.save_sync({planfile_id: remote_str})
                    if known_ticket_map is not None:
                        known_ticket_map[planfile_id] = remote_str
            return imported_count, result
        else:
            return _import_new_ticket(
                import_target or backlog,
                ext_data,
                integration_name,
                sync_state,
                imported_count,
                publish_to,
                store=store,
                target_sprint=next((name for name, section in sections.items()
                                    if section is (import_target or backlog)), "backlog"),
                observed_updated_at=observed_updated_at,
                known_ticket_map=known_ticket_map,
            ), updated_count
    except Exception as e:
        if store is not None and isolate_ticket_conflicts and _is_isolatable_ticket_conflict(e):
            local_ref = str(planfile_id or "")
            console.print(
                f"  [yellow]⚠️ Quarantined {local_ref or ext_data['id']} "
                f"(remote #{ext_data['id']}): {e}[/yellow]"
            )
            if quarantined_tickets is not None:
                quarantined_tickets.append(
                    {
                        "local_id": local_ref,
                        "remote_id": str(ext_data["id"]),
                        "reason": str(e)[:200],
                    }
                )
            return imported_count, updated_count
        console.print(f"  ✗ Failed to import {ext_data['id']}: {e}")
        if store is not None:
            raise
        return imported_count, updated_count


def _bind_sync_state(
    base_dir: Path, integration_name: str, backend, *, dry_run: bool
) -> SyncState:
    """Bind sync state, reconciling renamed provider routes read-only during dry-run."""
    sync_state = SyncState.from_backend(
        base_dir, integration_name, backend, dry_run=dry_run
    )
    if not dry_run or not sync_state.state_file.exists():
        return sync_state
    try:
        raw = sync_state.get_last_sync()
    except SyncStateRepositoryMismatch:
        return SyncState.from_backend(
            base_dir, integration_name, backend, dry_run=False, persist=False
        )
    if raw.get("repository_aliases"):
        return SyncState.from_backend(
            base_dir, integration_name, backend, dry_run=False, persist=False
        )
    return sync_state


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
    exclude_incident_noise: bool = False,
    timeout_seconds: float | None = None,
    isolate_ticket_conflicts: bool = False,
) -> None:
    """Sync tickets from external system to planfile."""
    deadline = (
        resolve_inbound_deadline(timeout_seconds, backend)
        if integration_name == "github" or timeout_seconds is not None
        else None
    )
    with bind_backend_deadline(backend, deadline) if deadline is not None else nullcontext():
        if deadline is not None:
            deadline.set_stage("repository_identity")
            deadline.check("repository_identity")
        sync_state = _bind_sync_state(
            Path(store.base_dir), integration_name, backend, dry_run=dry_run
        )
        known_ticket_map = _snapshot_ticket_map(sync_state)
        quarantined_tickets: list[dict[str, str]] = []
        imported_count = 0
        updated_count = 0
        sdk_store = (
            store
            if not v1_source_file
            and callable(getattr(store, "update_ticket", None))
            and callable(getattr(store, "create_ticket", None))
            else None
        )

        sprint, backlog = _load_sprint_and_backlog(store, v1_source_file, v1_data)
        sections = _load_sync_sections(store, v1_source_file, v1_data)
        # Reuse the snapshots returned by the compatibility loader so imports into
        # the backlog are the same objects that are persisted below.
        sections["current"] = sprint
        sections["backlog"] = backlog
        observed_updated_at: dict[str, str | None] | None = None
        if sdk_store is not None:
            # The compatibility loader may return mutable cached dictionaries.
            # Freeze the observed records before fetching from the remote backend.
            sections = deepcopy(sections)
            sprint = sections["current"]
            backlog = sections["backlog"]
            observed_updated_at = (
                _freeze_observed_updated_at(sections, sdk_store) if not dry_run else None
            )
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
        normalized_ticket_ids = (
            {str(value).strip() for value in (ticket_ids or []) if str(value).strip()} or None
        )
        if deadline is not None:
            deadline.set_stage("resolve_selection")
            deadline.check("resolve_selection")
        if normalized_ticket_ids:
            for section in lookup_sections.values():
                for local_id, ticket in (section.get("tickets") or {}).items():
                    if local_id in normalized_ticket_ids:
                        _validate_ticket_binding(ticket, integration_name, backend)
        selected_remote_ids = _resolve_selected_remote_ids(
            normalized_ticket_ids, lookup_sections, sync_state, integration_name,
            strict_local=integration_name == "github",
        )
        if deadline is not None:
            deadline.set_stage("provider_fetch")
            deadline.check("provider_fetch")
        is_unscoped = (
            normalized_ticket_ids is None
            and not remote_labels
            and not requested_sprints
        )
        sync_started_at = datetime.now(timezone.utc)
        since = _resolve_incremental_since(
            sync_state,
            integration_name,
            selected_remote_ids=selected_remote_ids,
            remote_labels=remote_labels,
            requested_sprints=requested_sprints,
        )
        external_tickets = _fetch_external_tickets(
            backend, integration_name, remote_labels, selected_remote_ids, since=since
        )
        if deadline is not None:
            pending_after_fetch = (
                [_ticket_trace_id(item) for item in external_tickets]
                if external_tickets
                else ()
            )
            deadline.check("provider_fetch", pending_tickets=pending_after_fetch)
        if external_tickets is None:
            return
        if not external_tickets:
            console.print(f"  [dim]ℹ️ No tickets to import from {integration_name}[/dim]")
            if not dry_run and is_unscoped:
                _save_sync_state_metadata(
                    sync_state,
                    inbound_cursor_at=sync_started_at.isoformat(),
                    quarantined_inbound_tickets=[] if since is None else None,
                )
            return

        work_tickets = [
            ext_ticket
            for ext_ticket in external_tickets
            if not (exclude_incident_noise and is_incident_noise(ext_ticket))
        ]
        completed_tickets: list[str] = []
        deferred_reconciliation_error: ValueError | None = None
        for idx, ext_ticket in enumerate(work_tickets):
            if deadline is not None:
                deadline.set_stage("local_projection")
                pending_ids = [_ticket_trace_id(item) for item in work_tickets[idx:]]
                try:
                    deadline.check(
                        "local_projection",
                        completed_tickets=completed_tickets,
                        pending_tickets=pending_ids,
                    )
                except SyncDeadlineExceededError:
                    if (
                        not dry_run
                        and (imported_count > 0 or updated_count > 0)
                        and sdk_store is None
                    ):
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
                    raise
            try:
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
                    normalized_ticket_ids,
                    import_target,
                    selected_remote_ids,
                    store=sdk_store,
                    observed_updated_at=observed_updated_at,
                    known_ticket_map=known_ticket_map,
                    isolate_ticket_conflicts=isolate_ticket_conflicts,
                    quarantined_tickets=quarantined_tickets,
                )
            except ValueError as exc:
                if str(exc) == "inbound_terminal_transition_requires_execution_reconciliation":
                    if deferred_reconciliation_error is None:
                        deferred_reconciliation_error = exc
                    continue
                raise
            completed_tickets.append(_ticket_trace_id(ext_ticket))

        if not dry_run and (imported_count > 0 or updated_count > 0) and sdk_store is None:
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
        if deferred_reconciliation_error is not None:
            raise deferred_reconciliation_error
        if not dry_run and is_unscoped:
            quarantine_arg = (
                quarantined_tickets
                if (since is None or quarantined_tickets)
                else None
            )
            _save_sync_state_metadata(
                sync_state,
                inbound_cursor_at=sync_started_at.isoformat(),
                quarantined_inbound_tickets=quarantine_arg,
            )


_INCIDENT_NAME_PATTERN = re.compile(
    r"^(\[(?:autocontrol|computer-use)[^\]]*\]|Runtime crash:|Auto-detected degradation:|Failed to run action:)",
    re.IGNORECASE,
)
_INCIDENT_LABEL_KEYWORDS = {
    "incident",
    "crash",
    "auto-detected",
    "degradation",
    "runtime-crash",
    "incident-report",
}


def is_incident_noise(ext_ticket) -> bool:
    """Return True if an external ticket represents raw runtime crash or degradation noise."""
    data = _extract_ticket_data(ext_ticket)
    name = (data.get("name") or "").strip()
    if _INCIDENT_NAME_PATTERN.search(name):
        return True
    labels = data.get("labels") or []
    for lbl in labels:
        clean_lbl = str(lbl).strip().lower()
        if clean_lbl in _INCIDENT_LABEL_KEYWORDS or clean_lbl.startswith("incident:"):
            return True
    return False


def _extract_ticket_data(ext_ticket) -> dict:
    """Extract standardized ticket data from external ticket (dict or Pydantic model)."""
    if hasattr(ext_ticket, "id"):
        fields_set = getattr(ext_ticket, "model_fields_set", None)
        priority = (
            {"priority": ext_ticket.priority}
            if hasattr(ext_ticket, "priority")
            and (fields_set is None or "priority" in fields_set) else {}
        )
        return {
            **priority,
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
            **({"priority": ext_ticket["priority"]} if "priority" in ext_ticket else {}),
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


def _inbound_status(ext_data: dict, integration_name: str, local_status=None) -> str:
    """Project GitHub's coarse lifecycle without erasing native execution state."""
    status = ext_data["status"]
    if integration_name != "github":
        return status
    if status not in {"open", "closed"}:
        raise ValueError(f"Unsupported GitHub issue state: {status!r}")
    # Native terminal reopening needs its own authorized store operation.
    # Failed/blocked/canceled all project to closed on outbound sync as well.
    if local_status in {"done", "canceled", "failed", "blocked"}:
        return local_status
    if status == "open":
        return local_status if local_status in {"in_progress", "review"} else "open"
    reason = (ext_data.get("metadata") or {}).get("state_reason")
    if reason == "completed":
        return "done"
    if reason == "not_planned":
        return "canceled"
    # A legacy/unknown reason proves closure, not successful completion.
    return "blocked"


def _update_local_ticket(
    sprint: dict,
    backlog: dict,
    planfile_id: str,
    ext_data: dict,
    updated_count: int,
    integration_name: str,
    publish_to: list[str] | None,
    store=None,
    observed_updated_at: dict[str, str | None] | None = None,
) -> int:
    """Update an existing local ticket from external data."""
    _reject_github_pull_request_url(integration_name, ext_data.get("url"))
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

    update_fields["status"] = _inbound_status(ext_data, integration_name, ticket.get("status"))
    remote_labels = list(ext_data.get("labels") or [])
    local_dedupe_labels = [
        lbl
        for lbl in (ticket.get("labels") or [])
        if isinstance(lbl, str) and lbl.startswith("dedupe:") and lbl not in remote_labels
    ]
    update_fields["labels"] = remote_labels + local_dedupe_labels
    if ext_data.get("url") and "github.com/" in str(ext_data["url"]):
        backend_ref["repository"] = str(ext_data["url"]).split("github.com/", 1)[1].split(
            "/issues/", 1
        )[0]
    sync = deepcopy(ticket.get("sync") or {})
    sync[integration_name] = backend_ref
    update_fields["sync"] = sync
    if store is not None:
        changes = {key: value for key, value in update_fields.items()
                   if key != "id" and ticket.get(key) != value}
        has_inner_id = bool(str(ticket.get("id") or "").strip())
        if not has_inner_id:
            changes["id"] = planfile_id
        if not changes:
            return updated_count
        execution = ticket.get("execution") or {}
        if ("status" in changes and changes["status"] in {"done", "canceled", "blocked", "failed"}
                and (execution.get("state") in {"running", "in_progress"}
                     or execution.get("assigned_to") or execution.get("lease_expires_at"))):
            raise ValueError("inbound_terminal_transition_requires_execution_reconciliation")
        expected_updated_at = (
            (
                observed_updated_at.get(planfile_id, ticket.get("updated_at"))
                if observed_updated_at is not None
                else ticket.get("updated_at")
            )
            if has_inner_id
            else None
        )
        updated = store.update_ticket(
            planfile_id, expected_updated_at=expected_updated_at,
            expected_snapshot=deepcopy(ticket), actor=f"sync:{integration_name}",
            reason=f"Inbound {integration_name} ticket {ext_data['id']}", **changes)
        if updated is None:
            raise ValueError(f"inbound_ticket_disappeared: {planfile_id}")
        ticket.update(updated.model_dump(mode="json"))
        if observed_updated_at is not None:
            observed_updated_at[planfile_id] = updated.updated_at
    else:
        ticket.update(update_fields)
        ticket.setdefault("sprint", default_sprint)

    console.print(f"  ✓ Updated: {planfile_id} from {ext_data['id']}")
    return updated_count + 1


def _import_new_ticket(
    backlog: dict,
    ext_data: dict,
    integration_name: str,
    sync_state,
    imported_count: int,
    publish_to: list[str] | None = None,
    store=None,
    target_sprint: str = "backlog",
    observed_updated_at: dict[str, str | None] | None = None,
    known_ticket_map: dict[str, str] | None = None,
) -> int:
    """Import a new ticket from external system."""
    _reject_github_pull_request_url(integration_name, ext_data.get("url"))
    new_id = f"{integration_name.upper()}-{ext_data['id']}"

    existing = (backlog.get("tickets") or {}).get(new_id)
    if isinstance(existing, dict):
        # Duplicate identity is an update, never authority to reschedule it.
        _update_local_ticket(backlog, {}, new_id, ext_data, 0,
                             integration_name, publish_to, store=store,
                             observed_updated_at=observed_updated_at)
        remote_str = str(ext_data["id"])
        if known_ticket_map is None or known_ticket_map.get(new_id) != remote_str:
            sync_state.save_sync({new_id: remote_str})
            if known_ticket_map is not None:
                known_ticket_map[new_id] = remote_str
        return imported_count

    priority = normalize_inbound_priority(ext_data)

    ticket_data = {
        # Legacy importers omitted this field, making the record invisible to
        # the typed store and ``ticket list/show``. Keep the generated local ID
        # as the canonical key in every physical sprint format.
        "id": new_id,
        "name": ext_data.get("name") or ext_data.get("title"),
        "description": ext_data["description"],
        "status": _inbound_status(ext_data, integration_name),
        "sprint": target_sprint,
        "assignee": ext_data["assignee"],
        "labels": ext_data["labels"],
        "priority": priority,
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

    tickets = backlog.setdefault("tickets", {})
    if not isinstance(tickets, dict):
        tickets = {}
        backlog["tickets"] = tickets
    if store is not None:
        from planfile.core.store import Ticket
        created = store.create_ticket(Ticket.model_validate(ticket_data), expected_absent=True)
        ticket_data = created.model_dump(mode="json")
    tickets[new_id] = ticket_data
    remote_str = str(ext_data["id"])
    sync_state.save_sync({new_id: remote_str})
    if known_ticket_map is not None:
        known_ticket_map[new_id] = remote_str

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


def check_sync_consistency(
    store,
    integration_name: str = "github",
    backend=None,
    v1_source_file=None,
    v1_data=None,
) -> list[dict[str, Any]]:
    """Flag ticket sync mappings disagreeing with backend state file or remote issues.

    Checks:
    - Ticket has sync mapping differing from state.yaml ticket_map.
    - Ticket has sync mapping but is missing from state.yaml.
    - State.yaml has ticket mapped but ticket is missing sync mapping.
    - If backend is supplied: remote ticket is missing (404) or closed while local is open.
    """
    sections = _load_sync_sections(store, v1_source_file, v1_data)
    store_dir = Path(getattr(store, "base_dir", "."))
    sync_state = (SyncState.from_backend(store_dir, integration_name, backend, persist=False)
                  if backend else SyncState(store_dir, integration_name))
    last_sync = sync_state.get_last_sync()
    state_map = last_sync.get("ticket_map") or {}

    discrepancies: list[dict[str, Any]] = []
    seen_ticket_ids = set()

    for _sprint_id, section in sections.items():
        tickets = section.get("tickets") or {}
        if not isinstance(tickets, dict):
            continue
        for ticket_id, ticket in tickets.items():
            if not isinstance(ticket, dict):
                continue
            seen_ticket_ids.add(str(ticket_id))
            sync_info = (ticket.get("sync") or {}).get(integration_name)
            ticket_remote_id = (
                str(sync_info.get("id"))
                if isinstance(sync_info, dict) and sync_info.get("id")
                else None
            )
            state_remote_id = state_map.get(str(ticket_id))
            if state_remote_id is not None:
                state_remote_id = str(state_remote_id)

            if ticket_remote_id and state_remote_id and ticket_remote_id != state_remote_id:
                discrepancies.append(
                    {
                        "ticket_id": str(ticket_id),
                        "kind": "state_mismatch",
                        "ticket_remote_id": ticket_remote_id,
                        "state_remote_id": state_remote_id,
                        "message": (
                            f"Ticket {ticket_id} has remote ID {ticket_remote_id} "
                            f"but state file has {state_remote_id}"
                        ),
                    }
                )
            elif ticket_remote_id and not state_remote_id:
                discrepancies.append(
                    {
                        "ticket_id": str(ticket_id),
                        "kind": "missing_state_mapping",
                        "ticket_remote_id": ticket_remote_id,
                        "message": (
                            f"Ticket {ticket_id} has remote ID {ticket_remote_id} "
                            f"but is missing from {integration_name}.state.yaml"
                        ),
                    }
                )
            elif not ticket_remote_id and state_remote_id:
                discrepancies.append(
                    {
                        "ticket_id": str(ticket_id),
                        "kind": "missing_ticket_mapping",
                        "state_remote_id": state_remote_id,
                        "message": (
                            f"Ticket {ticket_id} mapped to {state_remote_id} "
                            f"in {integration_name}.state.yaml but missing from ticket"
                        ),
                    }
                )

            effective_remote_id = ticket_remote_id or state_remote_id
            if backend and effective_remote_id and hasattr(backend, "get_ticket"):
                try:
                    remote = backend.get_ticket(str(effective_remote_id))
                    remote_status = getattr(remote, "status", None) or getattr(remote, "state", None)
                    if isinstance(remote, dict):
                        remote_status = remote.get("status") or remote.get("state")
                    local_status = str(ticket.get("status", "")).lower()
                    if (
                        remote_status
                        and str(remote_status).lower() == "closed"
                        and local_status in {"open", "in_progress", "in-progress"}
                    ):
                        discrepancies.append(
                            {
                                "ticket_id": str(ticket_id),
                                "kind": "remote_closed",
                                "remote_id": str(effective_remote_id),
                                "local_status": local_status,
                                "remote_status": str(remote_status),
                                "message": (
                                    f"Ticket {ticket_id} is {local_status} locally "
                                    f"but remote #{effective_remote_id} is closed"
                                ),
                            }
                        )
                except Exception as exc:
                    if "404" in str(exc) or "not found" in str(exc).lower():
                        discrepancies.append(
                            {
                                "ticket_id": str(ticket_id),
                                "kind": "remote_missing",
                                "remote_id": str(effective_remote_id),
                                "message": (
                                    f"Remote issue #{effective_remote_id} for ticket "
                                    f"{ticket_id} was not found (404)"
                                ),
                            }
                        )

    # Check for state entries pointing to non-existent local tickets
    for state_ticket_id, remote_id in state_map.items():
        if str(state_ticket_id) not in seen_ticket_ids:
            discrepancies.append(
                {
                    "ticket_id": str(state_ticket_id),
                    "kind": "orphaned_state_mapping",
                    "state_remote_id": str(remote_id),
                    "message": (
                        f"{integration_name}.state.yaml has mapping for "
                        f"{state_ticket_id} -> {remote_id} but ticket does not exist locally"
                    ),
                }
            )

    return discrepancies
