# Ticket 308: Retain the latest locator after bounded index repair

- **ID**: ticket-308
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION is the user request to continue the Planfile repair, test the result and publish through the independent Validator.

A fresh copy of the operational SQLite index held an older locator stamp than its committed source signature. With two changed sprints and one changed journal, cold repair reached the legacy archive scan and stopped at the byte budget. A successful bounded repair already reads the new locator, but another archive change can arrive before the maintenance loop observes the new index as current.

Publish that verified locator after bounded reconciliation using the existing exact-signature guard. Keep locator verification and repair behavior on a failed publication intact.

## Acceptance criteria

- [x] AC-01: Two consecutive deferred archive moves reconcile without a full identity or archive scan after reopening the store.
- [x] AC-02: Existing generations, locator removals and fallback repair keep their behavior.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 52/100 |
| Complexity | M |
| Estimated effort | 51 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
