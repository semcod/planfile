# Ticket 299: Allow multi-MB sprint index reconciliation and discovery stale retry

- **ID**: ticket-299
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Workstream**: application
- **Origin**: semcod/planfile#403 (P1) with SESSION_EXECUTION_AUTHORIZATION
- **Created**: 2026-11-19

## Goal and scope

Fix `HTTP 503 ticket_index_stale` rebuild loops on multi-MB `current.yaml` workloads (`semcod/planfile#403`):
- Raise `MAX_REPAIR_SECONDS` in `planfile/core/index_repair.py` from `2.0` to `8.0` so bounded incremental `reconcile_index` (invoked first by `server._repair_ticket_index()` and `_maintain_ticket_index()`) succeeds on ~7 MB `current.yaml` (~2.44s under normal host load) without falling back to a 200s full archive scan.
- Keep `GET /tickets/discovery` strictly read-only (`HTTP 503` with `Retry-After: 2` while stale) so maintenance completes incrementally in background and restores `HTTP 200` without archive rebuild loops.
- Add regression tests in `tests/test_index_repair.py` verifying multi-second `current.yaml` incremental repair, background `server._repair_ticket_index()` restoration to `GET /tickets/discovery` `HTTP 200`, and fail-closed `None` when `MAX_REPAIR_SECONDS` is exceeded.

## Acceptance criteria

- [x] AC-01: `reconcile_index` completes cleanly when `current.yaml` incremental reconciliation takes ~2.6s within the updated `MAX_REPAIR_SECONDS = 8.0` budget without invoking `_ticket_index_records` (full archive rebuild).
- [x] AC-02: Background `server._repair_ticket_index()` incrementally reconciles a stale multi-second `current.yaml` delta so `GET /tickets/discovery` recovers from `503` to `HTTP 200` with updated rows without touching `store.py` or `sqlite_index.py`.
- [x] AC-03: Unbounded deltas exceeding `MAX_REPAIR_SECONDS` still return `None` from `reconcile_index` and preserve `HTTP 503` (`Retry-After: 2`) on `/tickets/discovery`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
