# Ticket 218: Fix SQLite FD leaks, N+1 queries, uncached YAML loop parses, and unwired parameters

- **ID**: ticket-218
- **Owner**: agent:gemini
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-17
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requests continued performance and governance repairs across planfile. Fix SQLite file-descriptor leaks in `RetryQueue`, eliminate per-row SQLite queries inside loops in `SQLiteTicketIndex` and `DSLExecutor`, add mtime-keyed `@lru_cache(maxsize=256)` YAML loading across loop scans, wire unused optional parameters (`compact`, `interval_seconds`, `sprint`, `backend`), and record baseline standard pack adoption.

## Acceptance criteria

- [x] AC-01: `RetryQueue` closes SQLite connections via `contextlib.closing`, `SQLiteTicketIndex` batches `rebuild` and `apply` queries outside loops, `DSLExecutor` delegates sequence step execution without loop-level `.execute` calls, YAML loop parses use mtime-keyed `@lru_cache(maxsize=256)`, and `compact`, `interval_seconds`, `sprint`, and `backend` are wired and tested in `tests/test_sqlite_index_and_retry_perf.py`.
- [x] AC-02: `standard_pack_check.py` reports `findings=0` and `./project/governance-check.sh` passes (`GOV-PASS`).

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
