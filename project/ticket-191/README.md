# Ticket 191: Preserve Koru OpenCode repair input contract

- **ID**: ticket-191
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Workstream**: application

SESSION_EXECUTION_AUTHORIZATION: owner requested immediate error issues and Koru/OpenCode repair on 2026-10-05. PLF-107 / semcod/planfile#228; parent paxlet-com/willmux#17.

## Acceptance criteria

- AC-01: Explicit OpenCode provider and repair mode, isolated worktree, promotion, retry limit and verification survive SDK/store/CLI/API readback and partial updates.
- AC-02: Legacy tickets acquire no new repair defaults; malformed booleans are rejected.
- AC-03: Focused tests, genuine Koru contract readback and governance pass; independent protected delivery and installed readback remain separate evidence.

Validation: 36 focused tests, Ruff and governance pass. Actual Koru consumers preserve OpenCode selection, patch mode, branch promotion, retry limit and named verification; legacy patch fallback remains unchanged. Full suite: 1080 passed, 6 existing skips and 1 existing deprecation warning. Koru/OpenCode actual execution refused by the existing governed-shell guard (semcod/koru#672); no CLI was started.
