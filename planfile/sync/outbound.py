"""Fail-closed outbound batches for the CLI, using existing sync operations."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path

from planfile.sync.operations import (
    _backend_repository,
    _create_new_ticket,
    _save_sync_results,
    _ticket_external_id,
    _update_existing_ticket,
    _validate_ticket_binding,
    console,
)
from planfile.sync.receipts import publish_intent, record_receipt, successful_receipt
from planfile.sync.state import SyncState


@dataclass(frozen=True)
class OutboundSyncResult:
    """Batch outcomes; success does not imply a newly created remote issue."""

    succeeded: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    planned: tuple[str, ...] = ()


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
    failed = []
    planned = []
    pending_receipts = []

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
            succeeded.append(ticket_id)
            console.print(f"  ↺ Already published: {ticket_id} ({prior['receipt_id'][:12]})")
            continue
        try:
            _validate_ticket_binding(ticket, integration_name, backend)
            if external_id:
                _update_existing_ticket(
                    backend, ticket, ticket_id, external_id, integration_name, sync_state
                )
            else:
                _create_new_ticket(
                    backend, ticket, ticket_id, integration_name, sync_state, ticket_map
                )
            succeeded.append(ticket_id)
            reference = (ticket.get("sync") or {}).get(integration_name) or {}
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
            if "403" not in str(error) and "Forbidden" not in str(error):
                console.print(f"    [dim]Error details: {traceback.format_exc()}[/dim]")
            pending_receipts.append(
                (intent, operation, external_id, None, None, "failed", type(error).__name__)
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

    result = OutboundSyncResult(tuple(succeeded), tuple(failed), tuple(planned))
    if failed:
        raise OutboundSyncError(integration_name, result)
    return result
