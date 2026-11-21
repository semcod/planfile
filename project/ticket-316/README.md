# Ticket 316: Persist locator snapshot on rebuild and daily archive to prevent full-rebuild thrashing

- **ID**: ticket-316
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION is the user request to continue investigating live Planfile errors, implement governed fixes, test, merge independently via the Validator App, and deploy.

In production, `tickets.sqlite3` repeatedly got stuck in an infinite full-rebuild loop (`503 ticket_index_stale` on `/tickets/discovery` and `503 planfile_store_lock_timeout` on `PATCH`/`POST`) because `meta['source_locator_snapshot_v1']` fell behind `meta['source_signature']`:
1. When a full rebuild commits `signature_before` and then invokes `reconcile_index(store, index, signature_before, locator_snapshot=locator_snapshot)`, `locator_snapshot` was never persisted for `signature_before`, so any budget/contention abort left SQLite with a new `source_signature` and a stale `source_locator_snapshot_v1`.
2. When `_repair_ticket_index` finished a quiet full rebuild (`signature_before == signature_after`) or `_archive_history_daily` finished an incremental `archive_completed` sweep, `source_locator_snapshot_v1` was not persisted until the maintenance loop polled again.
3. `persist_locator_snapshot` used a `0.05s` SQLite timeout that dropped snapshot persistence under brief WAL contention, and `reconcile_index` opened a separate read-write `index._connection()` per changed sprint while holding `store.mutation_lock()`.

Persist the verified `locator_snapshot` for `built_signature` before entering `store.mutation_lock()` in `reconcile_index` (guarded by the existing exact `source_signature` predicate), persist the verified current locator right after quiet full rebuilds in `_repair_ticket_index` and after daily archive sweeps in `_archive_history_daily`, raise `persist_locator_snapshot` default timeout to `1.0s`, and reuse a single read-only routing connection for changed-sprint identity reads inside `reconcile_index`.

## Acceptance criteria

- [x] AC-01: When `reconcile_index` is called after a rebuild with `built_signature` and matching `locator_snapshot` and aborts (budget or lock contention), `source_locator_snapshot_v1` is preserved for `built_signature` so a subsequent reopened stored-baseline repair reconciles without `_indexed_ticket_sprints` or another full rebuild.
- [x] AC-02: Quiet full rebuilds in `_repair_ticket_index` and incremental `archive_completed` updates persist the matching `source_locator_snapshot_v1` immediately while `source_signature` matches, preventing stale-locator fallback on subsequent deferred archive moves.
- [x] AC-03: All `tests/test_index_repair.py` and `tests/test_ticket_discovery.py` tests plus `./project/governance-check.sh --base origin/main` pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 56/100 |
| Complexity | L |
| Estimated effort | 61 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
