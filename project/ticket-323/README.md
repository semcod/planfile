# Ticket 323: Handle duplicate ticket_already_exists and terminal reconciliation errors per-ticket in inbound sync

- **ID**: ticket-323
- **Owner**: agent:antigravity (SESSION_EXECUTION_AUTHORIZATION from user request)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-23

## Goal and scope

Fix two live inbound sync aborts observed across the HeyAsa ecosystem:
1. When a canonical generated ID (e.g. `GITHUB-1022`) already exists in any loaded section (`sections`) without a reverse sync mapping, route it to `_update_local_ticket` instead of crashing in `_import_new_ticket` (`ticket_already_exists`), while preserving strict `expected_absent=True` protection against concurrent writes.
2. When an inbound terminal transition hits `inbound_terminal_transition_requires_execution_reconciliation` for a ticket with an active execution lease, log a warning, preserve the local execution state untouched, and continue syncing the remaining tickets in the repository.

## Acceptance criteria

- [x] AC-01: Pre-existing `GITHUB-<id>` tickets in any loaded sprint are updated cleanly without raising `ticket_already_exists`.
- [x] AC-02: Concurrent identity creation tests in `tests/test_sync_inbound_sdk_revision.py` continue to pass unchanged.
- [x] AC-03: `inbound_terminal_transition_requires_execution_reconciliation` skips only the affected ticket while preserving its execution state and importing/updating subsequent tickets.
