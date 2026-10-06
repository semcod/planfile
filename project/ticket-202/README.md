# Ticket 202: Reconcile silent broad exceptions in sync operations and outbound search

- **ID**: ticket-202
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Reconcile Doctor code-search findings (#420 / PLF-16991) regarding `python.silent-broad-except` in `planfile/sync/operations.py` (line 481) and `planfile/sync/outbound.py` (line 85). Ensure exceptions in `_resolve_selected_remote_ids` and `_search_remote_ticket` are logged with appropriate debug error signals rather than silently suppressed, while preserving mapping fallback behavior.

## Acceptance criteria

- [x] AC-01: In `planfile/sync/operations.py`, `_resolve_selected_remote_ids` logs a debug signal when `sync_state.get_remote_id` raises an exception instead of silently passing.
- [x] AC-02: In `planfile/sync/outbound.py`, `_search_remote_ticket` logs a debug signal when `search(marker)` raises an exception instead of silently returning None.
- [x] AC-03: Add comprehensive regression tests in `tests/test_sync_operations_error_signal.py`.
- [x] AC-04: Existing test suite passes and `./project/governance-check.sh` reports `GOV-PASS`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
