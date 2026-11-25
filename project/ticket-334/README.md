# Ticket 334: Emit committed Planfile API ticket outcomes to URTLog

- **ID**: ticket-334
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-25

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION covers the requested Heyasa and URTLog
follow-up in heyasa/heyasa#1100. Record the committed outcome of Planfile
HTTP completion and failure in URTLog using the ticket's repository identity.
Preserve the existing API and optional integration behavior.

## Acceptance criteria

- [x] AC-01: Committed HTTP completion and failure publish repository-scoped
  outcome logs without copying raw request data.
- [x] AC-02: Rejected writes, conflicting repository bindings and unavailable
  telemetry preserve the existing API contract.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 64/100 |
| Complexity | L |
| Estimated effort | 61 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
