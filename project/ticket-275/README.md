# Ticket 275: Keep the stale index window longer than a real rebuild

- **ID**: ticket-275
- **Owner**: agent:opencode-agent
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal

The Planfile HTTP API flapped between 200 and 503 while an index rebuild was running, even
though a coherent last-known-good snapshot existed the whole time.

Two defects sit behind that:

1. `_INDEX_REPAIR_STALE_WINDOW_SECONDS` was `300.0`, but a rebuild of the production store
   (about 22 358 tickets, 517 MB) takes **5-9 minutes** (measured twice on 2026-11-02:
   ~5 min and ~9 min). The window therefore expired *inside* the repair, and machine callers
   were answered `503`.
2. `_bounded_stale_index_response()` never received `require_fresh`, so a caller that asked
   for freshness was served a **stale** body with `200` and `X-Planfile-Index-State: stale`.
   The freshness guarantee only covered the in-memory cache path.

## Change

- The stale window now covers a real repair (1 hour). It stays bounded: a permanently
  broken index still fails closed, and `require_fresh` never accepts stale data.
- `require_fresh=True` returns `None` from the stale helper so the request falls through to
  the explicit `503` instead of receiving stale content.

## Acceptance criteria

- [x] AC-01: a 20-minute-old coherent snapshot is served with `X-Planfile-Index-State: stale`
      instead of `503` (previously impossible: 300 s window).
- [x] AC-02: `require_fresh=true` never returns stale data - it answers `503`.
- [x] AC-03: the in-memory stale path keeps its existing `require_fresh` guard.

## Evidence

- `pytest tests/test_sqlite_ticket_index.py` -> 76 passed (includes the new
  `test_stale_index_survives_a_repair_longer_than_five_minutes_but_never_lies`).
- Live measurement before/after: `12/12` probes at 0.07-0.53 s once `current`, then `503`
  at 5-19 s during the next repair; the window is the difference between those two states.
