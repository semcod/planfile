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

Validation: 8 startup/retry/content regressions and one delivery-state feedback regression reproduced before fixes. After correction, 25 focused tests, Ruff and governance passed. Actual isolated GitHub diagnostic #221 retried a controlled outage at startup, reconciled a local SDK edit on restart, and closed the same issue on restart; each successful pass settled without feedback. Full combined-base suite: 963 passed, 6 existing skips. Independent protected publication remains pending.
