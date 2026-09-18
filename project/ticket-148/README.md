# Ticket 148: Make Planfile release availability explicit for runtime dependencies

- **ID**: ticket-148
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: The user authorized execution of the remaining
Planfile Issues after the PR queue was cleared.

Make source, runtime and published package availability explicit and checked.

## Acceptance criteria

- [x] AC-01: Release metadata records source, runtime and published versions.
- [x] AC-02: The checker detects a source version newer than the published pin.
- [x] AC-03: The checker validates the declared Python compatibility range.
- [ ] AC-04: Focused tests and the managed governance check pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
