# Ticket 163: Restart Planfile through serve on the same port

- **ID**: ticket-163
- **Owner**: human:tom
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-27
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — user requested automatic restart on the same port through serve.

## Goal and scope

`planfile serve --port PORT` starts when free and restarts an identified Planfile server when occupied. Support the observed local Docker publication (Planfile uvicorn container) and locally managed serve processes. Preserve unrelated listeners; bound shutdown and startup waits; never escalate privileges or kill by port alone. Preserve Docker configuration on restart. Existing Koru ticket-322 remains blocked independently; this repository has no active competing writer.

## Acceptance criteria

- [x] AC-01: Free endpoint starts normally; occupied verified Planfile endpoint restarts on the same port.
- [x] AC-02: Local Docker Planfile container restarts by immutable container ID and keeps its configuration; unrelated or ambiguous listeners are refused.
- [x] AC-03: Local managed server restart handles stale state and process identity without signaling unrelated processes.
- [x] AC-04: Failure returns nonzero; regression, focused CLI and governance checks pass.

## Delivery

Implementation and tests in the allocated canonical worktree; local commit, PR and independent protected validation. No self-merge. A restart does not install new code into an existing Docker image.

## Validation

Same-port replacement tested with two real CLI processes and HTTP requests on a disposable port; Docker calls tested with exact-ID, readiness, ownership and remote-context cases. Focused CLI regression, Ruff and managed governance passed. Local Linux process takeover requires a record from this version; older unrecorded processes need one manual stop. Docker restart retains its existing image/options. Protected publication pending.
