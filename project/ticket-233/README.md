# Ticket 233: Restore model compatibility and canonical DSL ticket integration

- **ID**: ticket-233
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-22

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested stale Planfile PR/issue work and continued. Issue282 is a reproduced dependency of issue281 and onedev-agent ticket614 qualification. On unchanged main, Python3.10.20 reports 13 failed, 1317 passed and 12 skipped. Ten failures directly identify a missing TicketExecutor compatibility import. This ticket changes only planfile/models.py; foreign ticket231 source and lease remain untouched. Separate DSL errors remain outside this repair.

## Acceptance criteria

- [x] AC-01: Legacy TicketExecutor/TicketOutputs imports resolve to the canonical classes; decomposition, semantic, authoritative DSL creation and blocked-query diagnostic regressions pass.
- [ ] AC-02: Governance, relevant checks and independently controlled exact-head publication pass. Remaining DSL source errors are preserved as separate blockers, without fake full-suite success.

## Tracking boundary

This is a bounded compatibility repair, not a claim that all producer qualification or runtime deployment is complete. Receipt home: primary .subactor/receipts/ticket-233-model-exports.

## Local evidence

All 27 existing decomposition and semantic tests pass after the alias repair; legacy aliases are identical to canonical core.models classes. Governance and targeted Ruff pass. Full baseline qualification on unchanged main reports 13 failures/1317 passes/12 skips; the separate DSL and branch-ownership blockers are not waived by this repair. Publication remains conditional on protected checks.

## Accepted continuation scope2026-10-23

The root observer repair Autonom179 independently merged and was deployed with unchanged freshness/completeness/trust controls and cross-UID/clear-path canaries. A fresh complete owner-free observation plus exact legacy CAS applied the already confirmed231 handoff. Its original16 dirty files remain content-addressed and unchanged; broad refactor231 is BLOCKED with its recovery-only reservation released. Minimal legacy intent cannot emit the newer native continuity form; an explicit bounded recovery checkpoint records this diagnostic and no implementation proceeded in231.

The same user publication request now includes the three original DSL regressions in this ticket's clean checkout, solely planfile/dsl/executor.py. No broad refactor source is imported. Scope budgets now cover two implementation files/two components, with unchanged dependency/interface limits. Existing original regression assertions and all protected gates remain required.

## Requalification after bounded DSL repair

45 existing focused tests pass. Full local source qualification reports1330passed/12skipped/0failed in115.83s; the three original DSL failures are repaired with their original assertions unchanged. Governance passes. Protected hosted/offline/native matrix, reviewed verifier657 activation and exact retained-branch reconciliation remain required before independent merge.
