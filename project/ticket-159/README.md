# Ticket 159: Fix priority weighting for medium priority tickets in ticket sorting

- **ID**: ticket-159
- **Owner**: human:tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-27
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION

## Goal and scope

Fix priority weighting and normalization for `medium` priority tickets in Planfile:
1. Include `medium` (weight 2) in `Planfile._ticket_sort_key` priority mapping alongside `normal` (weight 2), preventing tickets with `priority: "medium"` from receiving default weight 99 (which sorted them behind `low` priority tasks).
2. Normalize priority case and whitespace in `_ticket_sort_key` lookup.
3. Normalize priority aliases (`medium`, `med`) to `normal` in `planfile/core/models/ticket.py` (`Ticket` model validator).
4. Add unit test coverage in `tests/test_priority_weighting.py` verifying priority normalization and relative sorting order.

## Acceptance criteria

- [x] AC-01: `Planfile._ticket_sort_key` assigns weight 2 to `medium` priority tickets, ranking them ahead of `low` (weight 3).
- [x] AC-02: `Ticket(id="PLF-1", priority="medium")` normalizes priority to `"normal"`.
- [x] AC-03: Regression tests in `tests/test_priority_weighting.py` pass.
- [x] AC-04: `./project/governance-check.sh` passes (`GOV-PASS`).

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
