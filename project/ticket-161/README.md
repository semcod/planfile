# Ticket 161: Hash full outbound ticket content before receipt deduplication

- **ID**: ticket-161
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-27

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested continued repairs, tests and protected publication on 2026-09-27. Bounded continuation of PLF-086 / GitHub174. WUP PLF-137 activation was synchronized, but appending its result after character4096 in the parent description yielded an old success receipt while GitHub174 kept the previous body. Hash full outbound content before deduplication; keep receipt projections bounded. No provider bypass, shared runtime replacement or unrelated source edits.

## Acceptance criteria

- [x] AC-01: Distinct tails beyond the old truncation limits have distinct publication identities.
- [x] AC-02: A long-description update reaches the existing issue once; unchanged retry is deduplicated and legacy receipt migration does not create another issue.
- [ ] AC-03: Focused regressions, governance and protected exact-head tests pass before independent publication.

## Tracking boundary

Parent: https://github.com/semcod/planfile/issues/174. Runtime activation: https://github.com/semcod/wup/issues/19. Raw observations remain in private recovery storage.

Validation: six new regressions failed before the fix; all105 sync tests and Ruff pass after. Protected exact-head validation remains required.
