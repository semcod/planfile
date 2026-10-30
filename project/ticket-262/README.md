# Ticket 262: Index cross-sprint status reads for autonomous queue snapshots

- **ID**: ticket-262
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-30

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: autonomously repair and publish the requested
ecosystem throughput work. Current Control lifecycle reads fail as
`planfile_unavailable` even when health and open-ticket queries succeed.
Cross-sprint in-progress and blocked reads exceeded 6–10 seconds at limit one.
The deployed SQLite query plan scans tickets using the position index;
there is no index beginning with status. Add the missing ordered status index
and migrate existing disposable projections without changing ticket records.

## Acceptance criteria

- [x] AC-01: New and existing projections search by status in ticket order without a whole-ticket scan; data and pagination remain unchanged.
- [x] AC-02: Concurrent opens migrate idempotently, existing reads stay read-only after migration, and index regression checks pass.

Production rollout requires exact-head independent publication and an observed
runtime exercise. Tests or a source merge alone do not prove deployment.

Validation: 82 focused SQLite index and connection-lifetime tests passed.
Ruff and diff whitespace checks passed. Protected exact-head verification and
independent publication remain required before runtime adoption.
