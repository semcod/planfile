# Ticket 172: parallel ticket scheduling with dynamic file scoping and exclusion

- **ID**: ticket-172
- **Owner**: agent:Antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-28
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION ("przetetsuj na pilotazowych isssues z wybranych projektow w semcod/* i udoskonalaj rozwiązanie")

## Goal and scope

Refine Planfile scheduling for multi-agent and parallel autonomous queue execution:
1. Split comma-separated file paths in `next_tickets` file-scope check so multi-file string specifications don't bypass disjoint file detection.
2. Support `locked_files: set[str] | None = None` and `exclude_ids: set[str] | None = None` in `Planfile.next_tickets` to enable dynamic work-stealing parallel worker pools to query runnable tickets with no file conflicts against currently running tasks.
3. Support `status: str | None = "open"` filter in `Planfile.execution_waves` and `planfile.core.decompose.execution_waves`.

## Acceptance criteria

- [x] AC-01: `Planfile.next_tickets` splits comma-separated items and strips whitespace when inspecting ticket file scopes.
- [x] AC-02: `Planfile.next_tickets` accepts `locked_files` and `exclude_ids` parameters for lock-free parallel scheduling.
- [x] AC-03: `Planfile.execution_waves` and `planfile.core.decompose.execution_waves` accept `status: str | None = "open"` to partition active uncompleted tickets.
- [x] AC-04: Comprehensive unit tests in `tests/test_scheduler_parallel.py` and `tests/test_decompose.py` pass with 100% success.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
