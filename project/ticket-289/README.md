# Ticket 289: Bound scoped GitHub inbound sync with monotonic operation deadlines

- **ID**: ticket-289
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: user requested "wykonaj zalegle zadania https://github.com/semcod/planfile/issues"; resolves semcod/planfile#256 with protected Validator publication.

## Goal and scope

Bound scoped GitHub inbound synchronization (`sync_from_external` and `planfile sync github`) with a strict monotonic operation deadline (`time.monotonic()`) across repository identity resolution, target selection, provider reads (clamping PyGithub requester timeouts via `bind_backend_deadline`), and local ticket projection. Preserve existing CAS/lease state, prevent silent wall-clock stalls, emit structured `SyncDeadlineExceededError` diagnostics with single-line CLI JSON output on expiry, and leave `planfile/sync/github.py` untouched.

## Acceptance criteria

- [x] AC-01: Scoped GitHub inbound sync resolves an effective positive monotonic deadline (`--timeout`, `backend.config["sync_timeout_seconds"]`, `PLANFILE_SYNC_TIMEOUT_SECONDS`, default `60.0s`) and binds backend requester/issue reads via `planfile/sync/deadline.py` without touching `planfile/sync/github.py`.
- [x] AC-02: Expired deadlines during identity, selection, provider fetch, or local projection abort fail-closed with `SyncDeadlineExceededError`, record completed vs. pending tickets, exit non-zero cleanly via CLI with single-line JSON diagnostics, preserve existing ticket/lease state cleanly, and keep fast non-deadline `TimeoutError` failures wrapped as `sync_inbound_fetch_failed`.
- [x] AC-03: Focused unit/CLI tests (`tests/test_sync_inbound_deadlines.py`), existing sync inbound regressions, Ruff, `./project/governance-check.sh --base origin/main`, and `wellman check` pass cleanly.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
