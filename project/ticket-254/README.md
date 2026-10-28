# Ticket 254: Disambiguate numeric local selectors

- **ID**: ticket-254
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue user-requested Heyasa autonomy repair, tests and independent publication. Follow up confirmed selector collision after semcod/planfile PR312, within existing owner issue256 / local PLF-17304. No duplicate intake issue.

The public SDK accepts a numeric local ticket ID553 mapped to issue999. Selecting that local ID currently also reads issue553 and closes an unrelated mapped ticket. Resolve one meaning per selector and reject conflicting selected local mappings before remote reads. Explicit #553 / fixture/repo#553 remain remote selectors; retain unaffected provider, CAS, execution, sprint and label behavior.

## Acceptance criteria

- [x] AC-01: Numeric local selector changes only its mapped issue; explicit remote selectors remain available and unrelated snapshots stay identical.
- [x] AC-02: Conflicting local/ledger mappings fail before provider I/O; selected sync compatibility and governance pass.
- [ ] AC-03: Required current-head/base checks and independent publication succeed.

Confirmed failing probe: external planfile256-20261028/numeric-selector-probe.json. PR312 was independently merged at959224a9cc95fe0a73a0d26b285c6b17b7c55561 before the additional probe was evaluated. Its own lease has been retired by exact owner CAS after trusted merge readback; this material correction uses a separate native allocation.

## Validation

Six regressions failed on the merged PR312 source; eight control cases passed. After correction all76selected-read cases and683affected sync tests pass (199.17s for the full affected suite). Ruff and native governance pass. Required exact-head/base protected verification and independent publication remain pending. No provider credentials, runtime dependency or protected policy changed.
