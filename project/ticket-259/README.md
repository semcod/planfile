# Ticket 259: Bound success-fixture patience independently of radar timeout policy

- **ID**: ticket-259
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-29

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue autonomous repair, tests and independent publication. This is the bounded CI dependency of native258 / PR319 / Planfile316 / parentPLF-20347. Preserve the frozen dependent source and the foreign governance checkout255.

Protected Python3.10 verification of head14409c0/base6b3ec5f failed2 existing creation-advisory cases while1937 passed and12 skipped. Hosted3.10/3.13 succeeded. The fake child failed to return within production's1s deadline under host load. Prior257 addressed another instance of this scheduler-sensitive test pattern.

Give non-deadline success fixtures generous but finite assessment and bulk budgets. Explicit malformed-output, stalled-input, descendant-cleanup and bulk-deadline tests retain their short overrides and assertions. Change no production source or protected check.

## Acceptance criteria

- [x] AC-01: All radar contracts pass, including explicit timeout/cleanup/bulk deadline tests; success semantics no longer depend on1s subprocess startup.
- [ ] AC-02: Governance and exact-head/current-base protected CI pass, independent publication is read back, and frozen dependent PR319 is reconciled on the new base.

Local validation: all80 radar contracts passed through Testless with outcome accounting and targeted coverage at load average above130. Ruff and the managed session-start gate passed. Protected matrix publication remains pending.
