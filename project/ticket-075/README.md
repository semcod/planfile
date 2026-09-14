# Ticket 075: Synchronize archived GitHub tickets idempotently

- **ID**: ticket-075
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested that dependency and Planfile
quality issues be fixed, pushed and continued. The WUP integration exposed two
Planfile regressions: tickets archived after completion were omitted from
GitHub synchronization, and repeated synchronization duplicated priority
labels.

This ticket changes the sync collector and the GitHub label projection, with
regression tests. It does not alter credentials, ticket archival rules or
package dependencies.

## Acceptance criteria

- [x] AC-01: A mapped GitHub ticket in a `history-*` sprint is selected for
  outbound synchronization.
- [x] AC-02: Repeating a GitHub label update yields the same canonical labels
  and does not mutate the caller's ticket labels.
- [x] AC-03: Focused tests, Ruff and the managed governance gate are run on
  the exact delivery head.

## Validation evidence

- `uv run pytest tests/test_sync_routing.py tests/test_github_deduplication.py -q`: 6 passed.
- `uv run pytest tests/test_e2e_backlog.py -q` in an isolated project-installed environment: 6 passed.
- `uv run ruff check planfile/cli/groups/sync/core.py planfile/sync/github.py tests/test_sync_routing.py`: passed.
- `./project/governance-check.sh --base origin/main --head HEAD --actor agent`: passed.

## Tracking boundary

This directory contains the bounded intent and delivery evidence. Executable
changes and tests remain in their owned source paths.
