# Ticket 126: Ticket store skips entries missing an explicit id field

- **ID**: ticket-126
- **Owner**: agent:claude-code
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

SESSION_EXECUTION_AUTHORIZATION: user asked to work through the open sync
correctness backlog for this project ("zajmij się nimi") in an earlier turn
of this session; this ticket and its implementation are that authorized work.

## Goal and scope

`TicketStoreMixin._tickets_from_sprint_data` iterated `tickets_dict.values()`
and dropped the dict key entirely, so a sprint entry synced in from an
external source without its own `id` field (observed in this project's own
`.planfile/sprints/backlog.yaml`, where several GitHub-imported entries carry
only the map key as identity) silently failed `_ticket_from_data` and vanished
from every listing. Fix `_tickets_from_sprint_data` to fall back to the dict
key when `id` is absent, and to skip non-dict entries defensively instead of
raising.

Non-goals: no change to how entries get their `id` on write, no change to the
sync pipeline that produces id-less entries in the first place.

## Acceptance criteria

- [x] AC-01: A sprint dict entry with no `id` key loads using its map key as
      the ticket id, instead of being silently dropped.
- [x] AC-02: A non-dict entry in the tickets map is skipped instead of raising.
- [x] AC-03: Regression test added; `pytest tests/test_store_tickets_id_fallback.py`
      and the existing `tests/test_ticket_files.py` pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
