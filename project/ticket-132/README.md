# Ticket 132: Wire Planfile public comments into GitHub sync and load external issue mappings

- **ID**: ticket-132
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

## Goal and scope

Wire deliberately public Planfile comments to the configured GitHub issue
mapping. A public comment is queued explicitly with `planfile ticket comment`
and delivered by the normal GitHub sync; private ticket notes and descriptions
remain excluded. Mapped external issue records must remain usable for this
purpose even when their lifecycle status is outside the local ticket enum.

## Acceptance criteria

- [x] AC-01: Scope authorized in-session by the repository owner (`tak`).
- [x] AC-02: `ticket comment` queues an immutable public event for an exact GitHub issue mapping.
- [x] AC-03: `sync github` delivers pending public events idempotently and never copies private notes.
- [x] AC-04: External GitHub mappings remain resolvable when the stored status is `waiting_input` or `wont_fix`.
- [ ] AC-05: Focused tests and governance checks pass.

## Validation evidence

- `pytest -q tests/test_ticket_comments.py tests/test_sync_ticket_comments.py tests/test_cli_help.py tests/test_repository_routing.py tests/test_sync_scope.py tests/test_sync_routing.py tests/test_sync_managed_only.py tests/test_sync_receipts.py`: 52 passed.
- `pytest -q`: 607 passed, 6 skipped, 8 unrelated pre-existing failures in OQL configuration and project-path tests.
- Governance hooks: focused runs passed; full commit gate passed ownership checks.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
