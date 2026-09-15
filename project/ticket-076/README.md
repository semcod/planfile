# Ticket 076: Scoped GitHub result comments

- **ID**: ticket-076
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested Koru issue execution, testing and publication with result comments synchronized through Planfile. Implement an explicit public-comment outbox for one mapped GitHub ticket. Never project raw execution notes or synchronize unrelated tickets.

## Acceptance criteria

- [x] AC-01: Queue explicit public text against an exact local ticket and GitHub issue identity.
- [x] AC-02: Retry failed or ambiguous sends without changing the issue body or repeating execution; reject event and mapping drift.
- [x] AC-03: Focused tests, lint and managed checks pass before protected publication.

Validation: 9 tests passed; Ruff and the managed governance check passed. Protected publication remains pending.
