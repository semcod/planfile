# Ticket 233: Restore execution and output model compatibility exports

- **ID**: ticket-233
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-10-22

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested stale Planfile PR/issue work and continued. Issue282 is a reproduced dependency of issue281 and onedev-agent ticket614 qualification. On unchanged main, Python3.10.20 reports 13 failed, 1317 passed and 12 skipped. Ten failures directly identify a missing TicketExecutor compatibility import. This ticket changes only planfile/models.py; foreign ticket231 source and lease remain untouched. Separate DSL errors remain outside this repair.

## Acceptance criteria

- [x] AC-01: Legacy TicketExecutor/TicketOutputs imports resolve to the same canonical class objects; existing decomposition and semantic regression tests pass.
- [ ] AC-02: Governance, relevant checks and independently controlled exact-head publication pass. Remaining DSL source errors are preserved as separate blockers, without fake full-suite success.

## Tracking boundary

This is a bounded compatibility repair, not a claim that all producer qualification or runtime deployment is complete. Receipt home: primary .subactor/receipts/ticket-233-model-exports.

## Local evidence

All 27 existing decomposition and semantic tests pass after the alias repair; legacy aliases are identical to canonical core.models classes. Governance and targeted Ruff pass. Full baseline qualification on unchanged main reports 13 failures/1317 passes/12 skips; the separate DSL and branch-ownership blockers are not waived by this repair. Publication remains conditional on protected checks.
