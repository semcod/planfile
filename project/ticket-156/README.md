# Ticket 156: Isolated Python API demonstrations

- **ID**: ticket-156
- **Owner**: codex-monag-continuation-20260919
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-19
- **Planfile**: PLF-081
- **Issue**: https://github.com/semcod/planfile/issues/165

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested verified MONAG/Planfile fixes and publication, then continued execution. Fix only Python API demonstrations and the TicketLogger name argument they exercise. Ownership prerequisite PLF-082 was published in PR #167. Historical sample-like tickets remain untouched; their authorship is not established.

## Acceptance criteria

- [x] AC-01: Every executable Python API example uses a disposable queue and preserves caller files, including on failure.
- [ ] AC-02: Examples and logger calls match the supported API, regression/full tests and governed protected publication succeed.

## Verification

Ten regression tests pass, including subprocess execution of all seven examples and the shell runner from a real sentinel project, exception cleanup, and logger persistence. Full suite: 701 passed, 6 skipped. Ruff on the changed scope and governance passed. Protected publication receipts are recorded in the delivery checkpoint; GitHub issue #165 tracks completion.
