# Ticket 149: Distinguish GitHub rate limits from permission failures

- **ID**: ticket-149
- **Owner**: codex:monag-report-resume-20260919
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-19

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested completion and explicitly authorized taking over the staged operations.py change, improving it and publishing in an isolated worktree. The exact original patch is backed up in host recovery storage. Planfile PLF-076 / GitHub #153.

Preserve the existing quota-diagnostic improvement, replace account/token rotation suggestions with waiting for the provider retry window, distinguish ordinary permission denial, and retain original exception status/headers for existing outbound retry scheduling. Do not change ticket-137 outbound policy, dependencies or any unrelated primary edit.

## Acceptance criteria

- [x] AC-01: 403 quota exhaustion and 429 responses show rate-limit diagnostics, not missing-permission advice.
- [x] AC-02: Retry-After/reset metadata survives both create and update failures; do not replace the exception.
- [x] AC-03: Genuine access denial stays distinct, arbitrary response bodies and credentials are not rendered by the diagnostic helper.
- [ ] AC-04: Offline regressions, complete tests and governance pass; publish through protected verification.

## Validation

669 passed, 6 existing skips in the complete suite; 34 focused sync tests passed and 14 diagnostic cases passed after the final assertion refinement. Scoped Ruff, whitespace and managed governance passed. Preserve the externally created commit 4d68b4a and complete its existing PR154. Publication remains pending independent verification.
