# Ticket 303: Enable bounded coordination.idleTakeover in governance manifest for autonomous continuation

- **ID**: ticket-303
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: implements part 1 of `semcod/planfile#442` (operator-requested autonomous continuation for `semcod/planfile`).

Enable bounded `coordination.idleTakeover` (`enabled: true`, `idleMinutes: 15`, `leaseMinutes: 120`) in the target-owned `.governance/manifest.json` (matching `heyasa/heyasa` policy and `.governance/manifest.schema.json`), leaving locked `.governance/manifest.base.json` untouched. Once merged, expired or idle ticket worktrees (such as `ticket-301` on PR #440) can be continued cleanly through the sanctioned `.governance/idle_takeover.py takeover` controller instead of stalling on `GOV-CHANGE-LEASE-002`.

## Acceptance criteria

- [x] AC-01: `.governance/manifest.json` declares valid `coordination.idleTakeover` (`enabled: true`, `idleMinutes: 15`, `leaseMinutes: 120`) passing schema validation and `./project/governance-check.sh`.
- [x] AC-02: `.governance/idle_takeover.py observe` recognizes the enabled `coordination.idleTakeover` policy instead of reporting `Idle takeover disabled`.
- [x] AC-03: `wellman check` passes with zero errors and `.governance/manifest.base.json` remains untouched.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
