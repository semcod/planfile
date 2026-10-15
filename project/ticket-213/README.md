# Ticket 213: Regression coverage for bounded allocator evidence

- **ID**: ticket-213
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested continuation, repairs, tests and protected publication. Followup to PLF-18410 / ticket-212. Add disjoint regression tests for sprint identity cache and allocation preparation on main 6164415. PR260 deployment remains blocked by independent squash verification; these tests do not grant retrospective approval or change deployment controls.

## Acceptance criteria

- [x] AC-01: Source replacement, corrupt cache, prefix separation and source changes during rebuild are covered.
- [x] AC-02: Preparation occurs outside the mutation lock; changed or added oversized sources fail closed inside it.
- [x] AC-03: Optional cache write failures retain safe allocation and preparation is cleared on exit.
- [ ] AC-04: Focused tests and governance pass, with exact-head independent review for publication.

## Non-goals

No runtime implementation changes, validator changes, deployment, or alteration of ticket-212 ownership. Preserve its unresolved deployment checkpoint.

## Validation

18 new deterministic regression cases; 71 focused allocator, locking, concurrency and dedupe tests passed. Ruff and managed governance passed. Full suite and independent exact-head publication remain pending.
