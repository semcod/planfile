# Ticket 179: Preserved GitHub titles during readback

- **ID**: ticket-179
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION

SESSION_EXECUTION_AUTHORIZATION: user requested continuation, fixes and protected merge. Live PLF-024 update on subactor/onedev-agent#481 reproduced sync_readback_title_mismatch because GitHub deliberately preserves remote titles.

- [x] AC-01: Existing GitHub body updates preserve title and pass identity readback.
- [x] AC-02: Creates reject mismatched titles, including title-preserving backends; other backends retain strict update title checks.
- [x] AC-03: Failed update readbacks are excluded from succeeded counts.
- [ ] AC-04: Affected synchronization tests and governance pass; independent Validator binds publication head.

## Verification

Regression-first: 2 failures, 13 passes. Final affected synchronization suite: 141 passed, one existing PyGithub deprecation warning. Managed gate: 0 errors, 0 warnings. Includes wrong identity and missing-mapping replacement rejection, intentional remote title preservation and strict create readback. Publication and real remote canary remain pending.
