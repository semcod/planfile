# Ticket 205: Keep blocked Planfile tickets open on GitHub

- **ID**: ticket-205
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-08

## Goal and scope

PLF-119: blocked operational tickets were published as closed/completed before their work was finished. Correct the existing GitHub lifecycle projection and cover new issue creation, durable marker reuse and updates. Preserve other mappings. SESSION_EXECUTION_AUTHORIZATION: user requested repairs, tests, push and protected merge; one writer in this canonical checkout, session codex-root-planfile205-20261008.

## Acceptance criteria

- [x] AC-01: Blocked tasks create and remain open; syncing an existing closed issue reopens it; terminal and unsupported status behavior remains covered.
- [ ] AC-02: Managed and stack checks pass, exact-head independent publication succeeds, active adapter and only own operational projections are verified.

## Validation and delivery

78 focused tests pass, Ruff passes, managed governance gate passes. Full suite: 1170 passed, 6 skipped (203 seconds). Keep IN_PROGRESS / PUBLICATION through independent exact-head review and protected merge; activation/readback follows the merge.
