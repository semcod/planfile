# Ticket 324: Align inbound ticket lookup sprint order with store update lookup to prevent stale_ticket_snapshot

- **ID**: ticket-324
- **Owner**: agent:antigravity (SESSION_EXECUTION_AUTHORIZATION from user request)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-23

## Goal and scope

When a legacy ticket appears in multiple archived history sprints (e.g.
`history-2026-09-19` and `history-2026-10-18` in `semcod/tagi`, `semcod/nxdo`,
`semcod/prefact`), `_find_local_ticket` iterates `sections` in alphabetical
`_all_sprint_ids()` order and returns the older sprint snapshot, while
`store.update_ticket` resolves the sprint via `store._ticket_lookup_sprints(tid)`
(which hits the newer indexed sprint first) and raises `stale_ticket_snapshot`.

Align `_find_local_ticket` and the generated-ID fallback in
`planfile/sync/operations.py` with `store._ticket_lookup_sprints(ticket_id)` so
inbound sync always reads and compares against the exact sprint snapshot that
`store.update_ticket` will update.

## Acceptance criteria

- [x] AC-01: `_ordered_sprints_for_ticket` orders loaded `sections` using `store._ticket_lookup_sprints(ticket_id)` when available.
- [x] AC-02: `_find_local_ticket` and `_process_external_ticket` use `_ordered_sprints_for_ticket` so duplicate-sprint tickets resolve to the same physical sprint as `store.update_ticket`.
- [x] AC-03: Regression test in `tests/test_sync_inbound_resilience.py` verifies duplicate history sprints sync cleanly without `stale_ticket_snapshot`, and all existing `test_sync_inbound_sdk_revision.py` tests pass.
