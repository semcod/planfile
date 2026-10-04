# Ticket 185: Recover authorized file watch synchronization

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Workstream**: application

SESSION_EXECUTION_AUTHORIZATION: kontynuuj. Planfile PLF-106 / GitHub #218; parent PLF-098 / #202.

## Acceptance criteria

- AC-01: Reconcile existing file changes at startup; detect content even with preserved mtime.
- AC-02: Failed deliveries remain pending with bounded backoff and provider cooldown; edits during sync remain detectable.
- AC-03: Preserve explicit integration routing, once/failure status and local-only SDK boundary; actual scoped GitHub canary verifies restart/failure recovery.
- AC-04: Full tests, genuine exact-head/base OneDev and independent protected publication pass; installed source verified.

Validation:8 regression-first failures reproduced startup/retry/preserved-mtime boundaries. After correction,28 focused tests and952 full tests passed (6 existing skips). Ruff passed. Genuine scoped GitHub watch canary and protected publication remain pending.
