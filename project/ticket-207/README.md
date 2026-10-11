# Ticket 207: Advance inbound sync revision and reject stale SDK CAS writes

- **ID**: ticket-207
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-10-11

## Goal and scope

Advance inbound sync revision and reject stale SDK CAS writes to prevent lost updates and sync rollback (#252 / PLF-13804).

## Acceptance criteria

- [x] AC-01: Store `create_ticket` supports `expected_absent=True` to prevent collision overwrite.
- [x] AC-02: Store `update_ticket` supports `expected_snapshot` parameter to verify exact state before mutating.
- [x] AC-03: `_update_local_ticket` in sync operations routes through `store.update_ticket` with CAS validation and advances sync revisions.
- [x] AC-04: Active execution leases prevent stale sync rollback from overwriting running tasks.
- [x] AC-05: Tests in `tests/test_sync_inbound_sdk_revision.py` pass and governance check passes.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
