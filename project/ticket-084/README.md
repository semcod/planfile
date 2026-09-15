# Ticket 084: Harden repository routing and local-only ticket creation

- **ID**: ticket-084
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested execution of the Planfile
repairs in ticket order, including tests and protected publication.

## Goal and scope

Keep Planfile discovery bound to the checkout's Git repository and reject a
configured GitHub repository that disagrees with `origin`. A ticket-triggered
`--sync` must publish only the newly created/updated ticket and return a
non-zero result when the protected outbound adapter fails. Plain ticket
creation remains local-only.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [ ] AC-02: Discovery stops at nested repository boundaries and reports a
  configured GitHub/origin mismatch without initializing the wrong store.
- [ ] AC-03: `ticket create/update/delete --sync` passes exact ticket/sprint
  scope to the existing protected sync adapter; failures remain non-zero and
  local work stays recoverable.
- [ ] AC-04: Focused/full tests, lint and governance pass on the exact head;
  protected PR review/merge remains pending.

## Validation evidence

- `uv run pytest -q tests/test_repository_routing.py` — 5 passed on the
  rebased implementation.
- `uv run pytest -q` — 573 passed, 6 skipped, 1 warning after rebasing onto
  the current `origin/main`.
- `uv run ruff check planfile/project_paths.py
  planfile/cli/groups/ticket/commands.py tests/test_repository_routing.py` —
  passed.
- `./project/governance-check.sh --base origin/main --head HEAD --actor agent`
  — GOV-PASS.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
