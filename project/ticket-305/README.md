# Ticket 305: Use a verified prior locator during background index repair

- **ID**: ticket-305
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION is the request to continue, merge and test. Verify
the Planfile recovery against an isolated copy of the running store and publish
the corrected candidate through the protected process.

The previous prefix filter failed after removal of a legitimate locator for
`archive-*`. Use the bounded locator observed by the maintenance worker while
the source and index signatures agree. Skip unrelated archive reads when the
locator path and prior source stamp match. Keep the conservative proof for
generations without a matching observation.

## Acceptance criteria

- [x] AC-01: A matching prior locator lets the background repair handle an ordinary archive move without loading untouched backlog or legacy files.
- [x] AC-02: Removing an unrelated locator still selects the canonical copy after rebuilding. Tests cover both archive prefixes and both storage layouts.
- [x] AC-03: The managed governance gate passes and the maintenance loop passes the proof captured on a current index to the next stale repair.

## Tracking boundary

This directory records the scoped delivery and the exact verification conditions.
