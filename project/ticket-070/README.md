# ticket-070: Honor explicit MCP project routing

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Workstream**: application
- **Created**: 2026-09-13

SESSION_EXECUTION_AUTHORIZATION: User requested autonomous correction, tests and protected publication. Intake: https://github.com/semcod/planfile/issues/71; repository-scoped Planfile PLF-001. Prerequisite ticket-069 / PR #72 is merged.

Explicit project_path currently passes the allowed-root guard but YAML read, patch and sprint handlers still use the process-global project. Resolve those operations against the validated explicit directory. Omitted project_path retains the existing default store behavior. Do not change ticket CRUD routing, mutation capabilities, allowed roots, dependencies or global server cache.

## Acceptance criteria

- AC-01: Read, patch and sprint listing use project B when requested, even when default project A was already cached; A stays unchanged.
- AC-02: Missing explicit project files never fall back to A; relative explicit paths resolve correctly.
- AC-03: Outside-root and symlink directory escapes remain rejected; mutations still require their capability.
- AC-04: Omitted project_path preserves current default-project behavior.
- AC-05: Regression and repository tests, governance and protected publication pass; runtime deployment is reported separately.

Validation: 6 regression cases failed before the fix; all 22 MCP tests pass after it. Full Python 3.13 suite: 502 passed, 6 skipped. Managed governance: zero findings.
