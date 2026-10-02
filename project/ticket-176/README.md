# Ticket 176: Wire automatic bidirectional GitHub sync for all Planfile tickets

- **ID**: ticket-176
- **Owner**: antigravity / user-authorized maintenance
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-02

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested implementation, validation,
and protected merge of automatic bidirectional GitHub sync for Planfile tickets
(tracking GitHub #193 / PLF-094).
Provide an active caller workflow in .github/workflows/planfile-github-sync.yml
discoverable by GitHub Actions with hourly schedule, manual workflow_dispatch,
and push triggers for ticket and planfile paths. Call the reusable workflow
`semcod/planfile/.github/workflows/planfile-sync-reusable.yml@v0.1.126`. Ensure
failures are visible, two-way reconciliation is validated, and tests pass.

## Acceptance criteria

- [x] AC-01: Scope is approved by user execution authorization.
- [x] AC-02: Active caller workflow placed in .github/workflows/planfile-github-sync.yml with schedule, workflow_dispatch, and push triggers.
- [x] AC-03: Two-way reconciliation is observable, idempotent, and visible failure handling is covered by tests.
- [x] AC-04: Full sync tests and governance checks pass.

## Evidence

Relocated caller workflow from .github/planfile-github-sync.yml to .github/workflows/planfile-github-sync.yml so GitHub Actions discovers and runs the scheduled, manual, and push triggers. Added .github/workflows/planfile-github-sync.yml and .github/** to manifest workstream ownedPaths. Full pytest sync suite (116 tests) passed. Pinned governance checks pass with 0 errors and 0 warnings.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
