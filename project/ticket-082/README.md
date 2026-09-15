# Ticket 082: Make GitHub sync repository-bound and discover all active Planfile sprints

- **ID**: ticket-082
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested implementation of the
reported Planfile GitHub synchronisation repairs, in ticket order, with tests.

## Goal and scope

Make inbound and outbound GitHub synchronisation enumerate the real project
store, including declared custom sprints, and bind every mapping to the
configured repository. Imported records must remain visible to the ticket API
and a repeated sync must not create duplicates. This ticket is the first
bounded slice; comment event transport and broader routing remain follow-ups.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [x] AC-02: Sync collects integration-tagged tickets from current, backlog and
  non-history custom sprints without duplicating IDs.
- [x] AC-03: Imported tickets contain a valid local `id`, persist in the
  selected source sprint, and remain readable through `ticket list/show`.
- [x] AC-04: Sync state is atomic and repository-bound; mismatched repositories
  fail closed and legacy mappings migrate without credentials.
- [x] AC-05: Marker lookup cannot bind a ticket from another local store, while
  same-ticket retries remain idempotent.
- [x] AC-06: Focused regressions, full Python tests, lint and the managed
  governance check pass on the exact delivery head.

## Validation evidence

Validated on the ticket branch before publication:

- `uv run pytest -q tests/test_sync_state.py tests/test_sync_scope.py tests/test_sync_routing.py tests/test_github_deduplication.py tests/test_sync_failure_status.py tests/test_ticket_comments.py` — 41 passed.
- `uv run ruff check` on all changed sync/CLI files and regression tests — passed.
- `uv run pytest -q` — 552 passed, 6 skipped.
- `./project/governance-check.sh --base origin/main --head HEAD --actor agent` — GOV-PASS.

Inbound comment history remains intentionally outside this slice; the existing
explicit, fail-closed comment outbox is governed by ticket-076.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
