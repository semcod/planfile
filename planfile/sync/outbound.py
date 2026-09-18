"""Fail-closed outbound batches for the CLI, using existing sync operations."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path

from planfile.sync.operations import (
    _backend_repository,
    _create_new_ticket,
    _record_backend_ref,
    _save_sync_results,
    _ticket_external_id,
    _update_existing_ticket,
    _validate_ticket_binding,
    console,
)
from planfile.sync.receipts import publish_intent, record_receipt, successful_receipt
from planfile.sync.state import SyncState


def _is_rate_limit_error(error: Exception) -> bool:
    """Recognize primary, secondary and abuse-limit provider responses."""
    status = getattr(error, "status", None)
    message = str(error).lower()
    return status in {403, 429} or any(
        marker in message
        for marker in ("rate limit", "secondary rate", "abuse detection", "retry-after")
    )


def _external_reference(value: object) -> dict[str, str]:
    """Extract only stable identity fields from a provider result."""
    if isinstance(value, dict):
        source = value
        getter = source.get
    else:
        def getter(key: str):
            return getattr(value, key, None)
    return {
        key: str(item)
        for key in ("id", "url", "key")
        if (item := getter(key)) is not None and str(item).strip()
    }


def _recover_lost_create(
    backend,
    ticket: dict,
    ticket_id: str,
    integration_name: str,
) -> tuple[str, dict[str, str]] | None:
    """Recover one committed create from a unique repository-scoped marker."""
    search = getattr(backend, "search_tickets", None)
    if not callable(search):
        return None
    metadata = (ticket.get("metadata") or {}).copy()
    marker = str(metadata.get("planfile_id") or ticket_id).strip()
    if not marker:
        return None
    try:
        matches = list(search(marker) or [])
    except Exception:
        return None
    if len(matches) != 1:
        return None
    reference = _external_reference(matches[0])
    remote_id = reference.get("id")
    if not remote_id:
        return None
    candidate = {"id": ticket_id, "sync": {integration_name: reference}}
    try:
        _validate_ticket_binding(candidate, integration_name, backend)
    except ValueError:
        return None
    return remote_id, reference


def _verify_remote_readback(
    backend,
    ticket: dict,
    ticket_id: str,
    integration_name: str,
    remote_id: str,
) -> dict[str, str] | None:
    """Verify a provider readback when the backend exposes a getter.

    Backends without ``get_ticket`` remain compatible, but the caller does not
    treat the local mapping as proof of remote state. A present getter is
    fail-closed: an unavailable or mismatched readback turns the batch outcome
    into a failure and the durable mapping is retained for a safe retry.
    """
    getter = getattr(backend, "get_ticket", None)
    if not callable(getter):
        return None
    try:
        remote = getter(str(remote_id))
    except Exception as exc:
        raise RuntimeError("sync_readback_failed") from exc
    reference = _external_reference(remote)
    if reference.get("id") != str(remote_id):
        raise RuntimeError("sync_readback_id_mismatch")
    _validate_ticket_binding(
        {"id": ticket_id, "sync": {integration_name: reference}},
        integration_name,
        backend,
    )
    expected_name = ticket.get("name") or ticket.get("title")
    actual_name = None
    if isinstance(remote, dict):
        actual_name = remote.get("name") or remote.get("title")
    else:
        actual_name = getattr(remote, "name", None) or getattr(remote, "title", None)
    if expected_name and actual_name and str(expected_name) != str(actual_name):
        raise RuntimeError("sync_readback_title_mismatch")
    return reference


@dataclass(frozen=True)
class OutboundSyncResult:
    """Stable machine-readable outcome categories for one outbound batch."""

    succeeded: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    planned: tuple[str, ...] = ()
    created: tuple[str, ...] = ()
    reused: tuple[str, ...] = ()
    updated: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe result without provider responses or secrets."""
        return {
            "created": list(self.created),
            "reused": list(self.reused),
            "updated": list(self.updated),
            "failed": list(self.failed),
            "planned": list(self.planned),
            "succeeded": list(self.succeeded),
        }


class OutboundSyncError(RuntimeError):
    """Partial failure raised after preserving successful synchronization state."""

    def __init__(self, integration_name: str, result: OutboundSyncResult):
        self.result = result
        super().__init__(
            f"{integration_name} sync failed for {len(result.failed)} ticket(s) "
            f"({len(result.succeeded)} succeeded): {', '.join(result.failed)}"
        )


def sync_to_external(
    backend, tickets, dry_run: bool, store, integration_name: str, v1_source_file=None, v1_data=None
) -> OutboundSyncResult:
    """Attempt each outbound ticket, save successes, then report any failures."""
    sync_state = SyncState(
        Path(store.base_dir), integration_name, repository=_backend_repository(backend)
    )
    ticket_map = {}
    succeeded = []
    created = []
    reused = []
    updated = []
    failed = []
    planned = []
    pending_receipts = []

    if not dry_run:
        preflight = getattr(backend, "preflight", None)
        if callable(preflight):
            preflight(tickets)

    for ticket_id, ticket in tickets:
        if dry_run:
            planned.append(ticket_id)
            ticket_name = ticket.get("name") or ticket.get("title", "No title")
            console.print(f"  Would create/update: {ticket_id} - {ticket_name}")
            continue
        intent = publish_intent(ticket_id, ticket, integration_name, sync_state.repository)
        external_id = _ticket_external_id(ticket, ticket_id, integration_name, sync_state)
        operation = "update" if external_id else "create"
        prior = successful_receipt(Path(store.base_dir), integration_name, intent["idempotency_key"])
        # Create is the dangerous non-idempotent operation. Native stores have
        # a durable receipt projection for updates too; retain legacy v1's
        # historical replay behaviour until its source file is migrated.
        if prior is not None and (operation == "create" or v1_source_file is None):
            reused.append(ticket_id)
            succeeded.append(ticket_id)
            console.print(f"  ↺ Already published: {ticket_id} ({prior['receipt_id'][:12]})")
            continue
        try:
            _validate_ticket_binding(ticket, integration_name, backend)
            if external_id:
                update_kind = _update_existing_ticket(
                    backend, ticket, ticket_id, external_id, integration_name, sync_state
                )
                (created if update_kind == "created" else updated).append(ticket_id)
            else:
                try:
                    _create_new_ticket(
                        backend, ticket, ticket_id, integration_name, sync_state, ticket_map
                    )
                except Exception as error:
                    if _is_rate_limit_error(error):
                        raise
                    recovered = _recover_lost_create(
                        backend,
                        ticket,
                        ticket_id,
                        integration_name,
                    )
                    if recovered is None:
                        raise
                    recovered_id, recovered_ref = recovered
                    verified_ref = _verify_remote_readback(
                        backend,
                        ticket,
                        ticket_id,
                        integration_name,
                        recovered_id,
                    )
                    if verified_ref:
                        recovered_ref = verified_ref
                    ticket_map[ticket_id] = recovered_id
                    _record_backend_ref(ticket, integration_name, recovered_ref, recovered_id)
                    console.print(f"  ↺ Recovered existing: {ticket_id} → {recovered_id}")
                    reused.append(ticket_id)
                    succeeded.append(ticket_id)
                    pending_receipts.append(
                        (
                            intent,
                            operation,
                            recovered_id,
                            recovered_ref.get("url"),
                            recovered_ref.get("key"),
                            "succeeded",
                            None,
                        )
                    )
                    continue
                created.append(ticket_id)
            succeeded.append(ticket_id)
            reference = (ticket.get("sync") or {}).get(integration_name) or {}
            verified_ref = _verify_remote_readback(
                backend,
                ticket,
                ticket_id,
                integration_name,
                str(reference.get("id") or external_id or ""),
            )
            if verified_ref:
                reference = verified_ref
                _record_backend_ref(ticket, integration_name, verified_ref, str(reference["id"]))
            pending_receipts.append(
                (
                    intent,
                    operation,
                    str(reference.get("id") or external_id or "") or None,
                    reference.get("url"),
                    reference.get("key"),
                    "succeeded",
                    None,
                )
            )
        except Exception as error:
            failed.append(ticket_id)
            console.print(f"  ✗ Failed to sync {ticket_id}: {error}")
            if _is_rate_limit_error(error):
                console.print("    GitHub rate/abuse limit reached; stopping batch for safe retry.")
                break
            if "403" not in str(error) and "Forbidden" not in str(error):
                console.print(f"    [dim]Error details: {traceback.format_exc()}[/dim]")
            pending_receipts.append(
                (
                    intent,
                    operation,
                    external_id or ticket_map.get(ticket_id),
                    None,
                    None,
                    "failed",
                    type(error).__name__,
                )
            )

    if not dry_run:
        sync_state.save_sync(ticket_map)
        _save_sync_results(store, v1_source_file, v1_data, tickets=tickets)
        for intent, operation, remote_id, remote_url, remote_key, outcome, error_type in pending_receipts:
            record_receipt(
                Path(store.base_dir),
                intent,
                operation=operation,
                outcome=outcome,
                remote_id=remote_id,
                remote_url=remote_url,
                remote_key=remote_key,
                error_type=error_type,
            )

    result = OutboundSyncResult(
        succeeded=tuple(succeeded),
        created=tuple(created),
        reused=tuple(reused),
        updated=tuple(updated),
        failed=tuple(failed),
        planned=tuple(planned),
    )
    if failed:
        raise OutboundSyncError(integration_name, result)
    return result
