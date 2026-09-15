# Ticket 094: Project terminal statuses to GitHub closed state

- **ID**: ticket-094
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

## Goal and scope

Lock the GitHub lifecycle projection with offline evidence. Planfile has richer
terminal statuses than GitHub; every terminal value must close an issue, while
open and in-progress values remain open. Unknown values must not cause an
unreviewed state mutation.
The implementation adds the missing `failed` and `blocked` terminal mappings.

## Acceptance criteria

- [ ] AC-01: Offline fake-issue tests cover `done`, `completed`, `failed`,
  `blocked`, `canceled`, `cancelled`, `closed`, `open`, and `in_progress`.
- [ ] AC-02: Unknown status is a no-op and no live provider is contacted.
- [ ] AC-03: Governance, focused tests, and the full Python suite pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

## Limits

The change is scoped to the GitHub adapter. It does not claim provider
readback or billing correctness, and tests never contact GitHub.
