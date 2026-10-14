# Ticket 209: Planfile: resume archived unfinished ticket in Koru queue

- **ID**: ticket-209
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-10-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested backlog continuation. Address maskservice/c2004#486 / PLF-3019.
An unfinished ticket (failed or blocked) rotated into an archive/history sprint file remains excluded from `current` sprint even after `ready_ticket` updates its status to open and execution to ready, because it physically resides in an archive/history sprint file.
Improve supported resume/recovery contract in `ready_ticket` and `resume_ticket`:
1. When `ready_ticket` or `resume_ticket` is invoked on an unfinished ticket located in an archive/history sprint, automatically restore it to the `current` sprint via `store.move_ticket(ticket_id, "current")`, restoring native `runnable_report` and `next_ticket` admission.
2. Preserve immutability of completed/canceled tickets: reject readying/resuming tickets that are in terminal state (`done`, `canceled`, `cancelled`).
3. Add `planfile ticket resume <ticket_id>` CLI command and `resume_ticket` method on `Planfile`.
4. Add comprehensive regression tests for resuming archived unfinished tickets and rejecting completed tickets.

## Acceptance criteria

- [x] AC-01: `ready_ticket` and `resume_ticket` restore an archived unfinished ticket to the `current` sprint, making it visible to `runnable_report` and `next_ticket`.
- [x] AC-02: `ready_ticket` and `resume_ticket` reject attempts to ready or resume tickets in terminal states (`done`, `canceled`, `cancelled`), preserving immutability.
- [x] AC-03: Add `resume_ticket` method to `Planfile` and `resume` CLI command to `ticket_app`.
- [x] AC-04: Unit and integration tests verify the resume/recovery contract across both single-YAML and sharded storage modes.

## Validation

- Pytest: 5/5 tests in `tests/test_ticket_resume_archived.py` pass cleanly.
- Governance: `./project/governance-check.sh` reports `GOV-PASS: passed (0 errors, 0 warnings)`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
