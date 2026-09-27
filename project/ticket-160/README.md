# Ticket 160: Preserve sprint envelope extensions

- **ID**: ticket-160
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-27

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested continuation of the runtime-health backlog, tests and protected publication. Implement a bounded slice of PLF-086 / https://github.com/semcod/planfile/issues/174: preserve outer YAML fields during native save and outbound sync, including the sharded backend, while retaining concurrent tickets and existing conflict behavior. Reproduce before changing code. Do not attribute the Monag incident to this defect without evidence. Do not deploy a new global CLI or mutate production services. Legacy closed normalization already exists in main and needs verification, not duplication.

## Acceptance criteria

- [x] AC-01: Existing root extensions survive stale saves for current/backlog and outbound sync.
- [x] AC-02: Newer unrelated tickets and GitHub mappings survive; extensions retain their original location and current disk values.
- [ ] AC-03: Single and sharded storage regressions and protected checks pass.

## Tracking boundary

Parent task: PLF-086 / GitHub #174. Canonical audit: https://github.com/subactor/docs/blob/main/architecture/analysis/runtime-health.md. This slice does not close the unexplained historical loss or replace deployed-version verification.
