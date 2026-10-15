# Ticket 217: Revalidate allocator preparation races under mutation lock

- **ID**: ticket-217
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-15

## Goal and scope

PLF-18410 followup. SESSION_EXECUTION_AUTHORIZATION: user requests continued repairs, tests and protected merging. A source modification during cold allocator preparation currently aborts before acquiring the lock. Revalidate fresh authoritative state under the existing bounded locked fallback.

## Acceptance criteria

- [x] AC-01: A small source changed during preparation allocates above the fresh high-water mark.
- [x] AC-02: Large changed sources fail closed without reservation writes; unrelated parser errors propagate.
- [ ] AC-03: Regression suite, governance and independent protected delivery pass.

## Boundaries

One writer; maximum active session 120 minutes. No storage migration, changed identity rules or weakened rebuild bound. Cold-start latency remains separate followup work.

## Validation evidence

Before fix: 2 regression failures, 11 passes. After fix: 13 focused tests pass; changed files pass Ruff. Full suite and protected publication receipts are held outside the checkout.
