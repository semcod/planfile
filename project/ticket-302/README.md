# Ticket 302: Reject canonical URT backlog documents at the native payload boundary

- **ID**: ticket-302
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION from the ecosystem operator to test and repair the URT integration. Parent PLF-21814. CQRS-028 in semcod/planfile#431 requires a mapping step before native ticket submission. The published guard accepted the source evolution-plan manifest and its 33 raw proposals.

## Acceptance criteria

- [x] AC-01: Reject the canonical URT evolution-plan manifest and its raw proposal shape. Preserve mapped tickets and ordinary native payloads with similar individual fields.

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
