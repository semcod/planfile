# Ticket 158: normalize closed status for github synced tickets in planfile core models

- **ID**: ticket-158
- **Owner**: human:tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-27
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION

## Goal and scope

Normalize external issue states such as `closed` and `in-progress` in Planfile's `Ticket` model and GitHub sync:
1. Support `closed` as alias for `done` in `Ticket` model validation (Pydantic `field_validator(mode="before")`).
2. Support `in-progress` as alias for `in_progress`.
3. Normalize inbound GitHub issue states in `planfile/sync/github.py` mapping `closed` -> `done`.
4. Add unit test coverage in `tests/test_ticket_status_normalization.py` verifying status normalization for both strings and dicts.

## Acceptance criteria

- [x] AC-01: `Ticket(id="PLF-1", title="test", status="closed")` validates cleanly without ValidationError, assigning `status=TicketStatus.done`.
- [x] AC-02: `Ticket(id="PLF-2", title="test", status="in-progress")` normalizes to `TicketStatus.in_progress`.
- [x] AC-03: `planfile/sync/github.py` maps `closed` state to `"done"` during sync.
- [x] AC-04: Test suite `tests/test_ticket_status_normalization.py` passes.
- [x] AC-05: `./project/governance-check.sh` passes (`GOV-PASS`).

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
