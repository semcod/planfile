# Ticket 257: Deterministic bulk deadline radar test

- **ID**: ticket-257
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user asked to remove recurring load-sensitive
verification failures. `tests/test_ticket_radar.py::test_failure_bulk_deadline_preserves_remaining_tickets`
failed intermittently on `main` and on unrelated branches (ticket-256 PR 315: 1 pass in
4 runs; `main`: 2 of 3 passes at load average 50-70). It used a 0.35 s bulk deadline and a
0.2 s fake radar, so Python subprocess start-up time decided the outcome.

Test-only change; no production code is modified.

## Changes

- The fake radar answers its first call immediately and blocks on every later call.
- `BULK_SECONDS` and `ASSESSMENT_SECONDS` are set to 2.0 s, so the first call never
  depends on start-up speed and the remaining calls are cut by the bulk deadline.
- Assertions keep the original intent: total radar time is bounded, at most two radar
  calls happen, the first ticket is enriched, all other tickets keep their human text and
  every ticket plus its operational event is preserved.

## Acceptance criteria

- [x] AC-01: The test passed 6 of 6 consecutive runs at load average above 15.
- [x] AC-02: The whole `tests/test_ticket_radar.py` file passes.
- [x] AC-03: `./project/governance-check.sh` passes.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
