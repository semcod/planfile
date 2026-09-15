# Ticket 081: Preserve identity for imported external tickets after sync readback

- **ID**: ticket-081
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the owner requested autonomous execution,
testing, publication and continuation during this session.

An external ticket imported by `planfile sync` is currently written under a
synthetic key such as `GITHUB-14`, but its record lacks the canonical `id` and
`sprint` fields required by the current ticket projection. The command reports
success while `ticket show` and `ticket list` can omit the imported record after
the process ends. Existing records refreshed through the legacy path have the
same identity gap.

This ticket adds the canonical local identity at both import and update
boundaries and covers the behavior with focused sync regression tests. It does
not redesign external routing, scoped synchronization, status translation, or
the independent ticket-radar worktree.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [ ] AC-02: New external imports persist `id` equal to the local synthetic
  key and `sprint: backlog`, so readback through the ticket projection returns
  the imported record.
- [ ] AC-03: Existing legacy imported records receive the same identity fields
  during refresh without losing backend-specific sync references.
- [ ] AC-04: Focused tests, the full Python suite, Ruff, whitespace checks and
  the managed governance gate pass on the exact implementation head.
- [ ] AC-05: A protected PR is reviewed and merged, with the exact merged head
  verified before ticket closure.

## Validation evidence

- Focused sync regression suite: `5 passed`.
- Full locked Python suite: `538 passed, 6 skipped, 11 warnings`.
- Ruff on changed Python paths: passed.
- `git diff --check`: passed.
- Managed governance check on the accepted base: `GOV-PASS`.
- Commit is currently held by the fail-closed worktree overlap guard because
  the preserved `feat/ticket-radar` worktree also changes
  `planfile/sync/operations.py`.

## Implementation boundary

Owned source paths are `planfile/sync/operations.py` and
`tests/test_sync_routing.py`. The ticket intent is the authoritative scope;
the unrelated dirty `ticket-radar` worktree remains preserved and must not be
stashed, deleted or included in this diff.

## Tracking boundary

This directory contains the reviewed intent and delivery evidence. Optional
participant prose and raw command logs are not required delivery output.
