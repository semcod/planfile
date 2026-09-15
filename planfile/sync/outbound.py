"""Fail-closed outbound batches for the CLI, using existing sync operations."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path

from planfile.sync.operations import (
    _create_new_ticket,
    _save_sync_results,
    _ticket_external_id,
    _update_existing_ticket,
    console,
)
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
    sync_state = SyncState(Path(store.base_dir), integration_name)
    ticket_map = {}
    succeeded = []
    failed = []
    planned = []

    for ticket_id, ticket in tickets:
        if dry_run:
            planned.append(ticket_id)
            ticket_name = ticket.get("name") or ticket.get("title", "No title")
            console.print(f"  Would create/update: {ticket_id} - {ticket_name}")
            continue
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
            succeeded.append(ticket_id)
        except Exception as error:
            failed.append(ticket_id)
            console.print(f"  ✗ Failed to sync {ticket_id}: {error}")
            if "403" not in str(error) and "Forbidden" not in str(error):
                console.print(f"    [dim]Error details: {traceback.format_exc()}[/dim]")

    if not dry_run:
        sync_state.save_sync(ticket_map)
        _save_sync_results(store, v1_source_file, v1_data)

    result = OutboundSyncResult(tuple(succeeded), tuple(failed), tuple(planned))
    if failed:
        raise OutboundSyncError(integration_name, result)
    return result
