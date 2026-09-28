# Ticket 166: Align historical ticket update selection with reads

- **ID**: ticket-166
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — user authorizes repairing Koru dependencies and protected publication/merge; continued 2026-09-28.

## Goal and scope

Fix Koru backlog reconciliation failing `expected_updated_at` when a ticket ID appears in multiple historical Planfile sprints. Preserve history and CAS guards; make exact lookup and update select the same authoritative durable record, with consistent indexed and unindexed reads.

## Acceptance criteria

- [x] AC-01: A get/update round trip updates the selected historical record and leaves duplicate siblings unchanged.
- [x] AC-02: Current-sprint precedence and stale-revision rejection remain intact.
- [x] AC-03: Indexed and unindexed lookups agree with updates; regression tests and managed governance checks pass.

## Delivery

Bounded session: maxActiveMinutes=120, checkpointMinutes=30. Publish through the independent protected controller. No changes to Koru's active source checkout or other agents' Planfile scopes.

## Validation

64 focused storage, concurrency, SQLite index and archive tests pass (including 18 new regression cases); Ruff and the managed governance gate pass. Regression failed before the fix with `ticket_updated_at_precondition_failed`.
