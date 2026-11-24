# Ticket 333: Defer the workspace alias index for local ticket observations (PLF-29386)

- **ID**: ticket-333
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-24

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue workspace PLF-25979 and resolve the observed delay in Planfile queue inspection. The uritime/urtlog queue walked 852 repositories without looking up a foreign slug. The scoped change keeps target observations, ownership checks and resolution precedence.

## Acceptance criteria

- Local targets avoid unrelated workspace observations in the executable queue and reconciliation.
- A foreign repository under a differently named directory still resolves, and repeated references use one index per query.
- Verify unchanged dispositions and elapsed time through the ordinary CLI on the affected repository.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 56/100 |
| Complexity | M |
| Estimated effort | 57 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
