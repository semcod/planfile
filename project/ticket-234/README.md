# Ticket 234: Declare infrastructure ownership for scheduled sync inputs

- **ID**: ticket-234
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-23

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the repository owner requested continued backlog work and protected merge ("to scal i kontynuuj, usun te stare"). Prior233 delivery and exact five-ref discard are complete. Issue280 requires a separate admitted repair of scheduled sync, including only qualified repository queue rows and behavior tests. Neither committed queue input currently has a declared workstream owner. This newly allocated governance ticket declares the exact future infrastructure inputs before that implementation, using one manifest delta. The allocator's unresolved:human field was a placeholder on our own newly allocated scaffold, not a foreign ownership handoff.

## Acceptance criteria

- [x] AC-01: Infrastructure ownedPaths adds only .planfile/sprints/backlog.yaml, .planfile/sprints/current.yaml and tests/test_scheduled_github_sync_workflow.py; all other manifest content is unchanged.
- [ ] AC-02: Managed governance, required original checks and independent exact-head protected publication pass.

## Tracking boundary

Preparation for #280, not closure of it. No schedule is enabled and no legacy queue records or workflow behavior change in this ticket. Canonical relative checkout and real source lease bind this writer. Blocked231's17dirtyfiles and primary operational data remain preserved. Receipts: primary .subactor/receipts/ticket-234-sync-ownership.

## Local validation

The exact JSON delta is three infrastructure ownedPaths additions; every other manifest value is unchanged. Managed governance and git diff --check pass. Original hosted/native checks and independent exact-head protected merge remain required; #280 stays open for the subsequent infrastructure implementation and canary.
