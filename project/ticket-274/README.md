# Ticket 274: Serve the last complete ticket index to machine callers

- **ID**: ticket-274
- **Owner**: agent:opencode-agent
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-02
- **Planfile**: PLF-22058

## Goal and scope

Measured on the deployed service: the ticket API answered **6 of 12 probes**
twenty seconds apart (`200 503 503 200 200 200 503 503 timeout 200 200 200`).

Cause: a full view (`/tickets?sprint=current`, the default) has no durable
fallback, so while the projection is being repaired it answered
`503 ticket_index_repair_pending`. Only a **browser** user agent was allowed to
read the last complete index, and only inside a **30 s** window. Every machine
caller - campaigns, tooling, this session's probes - therefore saw the same
query succeed or fail depending on its user agent and on the moment.

Scope: `planfile/api/server.py`, `tests/test_sqlite_ticket_index.py`.

## Acceptance criteria

- [x] AC-01: A full view may serve the last complete projection for as long as a
      repairing index would have been acceptable (`_INDEX_REPAIR_STALE_WINDOW_SECONDS`),
      not just the 30 s dashboard window, and marks it
      `X-Planfile-Index-State: stale`.
- [x] AC-02: `require_fresh=true` is never served a stale body: it bypasses both
      the response cache and the stale projection, and waits (503) or answers
      from live sources without the stale marker.
- [x] AC-03: Summary and operational views keep their fresh durable fallback;
      the existing fail-closed tests for an expired projection still pass.

## Evidence

- `pytest tests/test_sqlite_ticket_index.py` -> 75 passed (new:
  `test_full_view_serves_the_last_complete_index_to_a_machine_caller`).
- Measurement that motivated it: 6/12 probes available, recorded in PLF-22058.

## Non-goals

- Making the projection cheaper to rebuild, or coalescing invalidations; those
  remain in PLF-22058.
