# Ticket 301: Incremental archive-move recovery in index_repair without full rebuild

- **ID**: ticket-301
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user explicitly instructed sequential remediation (`kolejno`) starting with the live Planfile `HTTP 503 ticket_index_stale` / `.store.lock` outage blocking Heyasa, Willman and Coding Agent.

Live diagnosis on `subactor-planfile:0.1.127-2750d37` (28,772 tickets across 109 sprints, 922 MB `tickets.sqlite3`):
1. Whenever auto-archive moves completed tickets from `current.yaml` to `history-YYYY-MM-DD.yaml`, `store.py` skips `_finish_index_mutation`, leaving 2 sprints (`current` + `history-YYYY-MM-DD`) and `history-locations.yaml` ahead of `tickets.sqlite3`.
2. Background `_repair_ticket_index()` calls `reconcile_index(store, index)` -> `_stored_baseline()`, which unconditionally returns `None` when `history-locations.yaml` changed, when `len(changed) > 1`, or when a new daily `history-YYYY-MM-DD.yaml` sprint file is created.
3. That forces a >200s full 922 MB archive rebuild on every completed ticket (~24.5 GB read / 6.5 GB write per 10 min, `.store.lock` timeouts, continuous `503 ticket_index_stale`).

Keep `planfile/core/store.py` and `planfile/core/sqlite_index.py` untouched (reserved by active foreign tickets `ticket-286` and `ticket-296`). Fix `planfile/core/index_repair.py` so stored-baseline incremental repair safely reconciles bounded multi-sprint archive moves (including newly created daily history files and `history-locations.yaml` updates verified against indexed ticket sprints) while preserving fail-closed fallbacks on tampered/ambiguous locators, missing locator files, external races, and over-budget deltas.

## Acceptance criteria

- [x] AC-01: Background `_repair_ticket_index()` reconciles an auto-archive move (`current` -> `history-YYYY-MM-DD`, including newly created daily history file and `history-locations.yaml` update) incrementally with zero full archive scans and restores `GET /tickets/discovery` to HTTP 200.
- [x] AC-02: Stored-baseline locator recovery fails closed (falls back to full rebuild) when `history-locations.yaml` is missing while stored signature had one, when locator changes affect sprints outside the bounded changed-sprint set, or when locator changes occur without any changed sprint.
- [x] AC-03: All existing `tests/test_index_repair.py` invariants (explicit-baseline `budget="locator"`, `damage="locator"`, external races, byte/ticket/time caps) continue passing alongside new archive-move tests.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
