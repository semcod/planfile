# Ticket 090: Make external publish receipts durable and idempotent

- **ID**: ticket-090
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the owner requested continuation, repair,
testing, publication and protected merge of Planfile tickets in order.

Publish to GitHub/other external backends must leave a repository-bound receipt
that survives restart. A successful retry of the same ticket payload must not
call the remote create/update operation again; a changed payload gets a new
digest-bound attempt. Receipt data contains no credentials or raw exception
history.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [x] AC-02: Receipt records bind integration, repository, ticket, operation,
  outcome and sanitized remote reference to a deterministic idempotency key.
- [x] AC-03: Restart/retry, conflict, dry-run and failure paths are explicit;
  duplicate successful retries do not issue a second remote mutation.
- [ ] AC-04: Focused/full tests, lint, governance and exact-head Validator
  approval/merge pass.

## Tracking boundary

Validation: `uv run pytest -q` — 577 passed, 6 skipped, 1 warning; focused
receipt/failure tests — 17 passed; Ruff and managed governance — GOV-PASS.

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
