# Ticket 337: Handle wrapped schema discovery output in native CI

- **ID**: ticket-337
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-25

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION covers the test regression exposed by the
protected OneDev job for Planfile PR #452. The longer native scratch path
causes Rich to wrap the schema type label while the command still selects
the expected local config. Keep the repair within the schema discovery tests.

## Acceptance criteria

- [x] AC-01: The test verifies local config selection consistently at narrow
      and wide console widths, including the native executor scratch layout.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 60/100 |
| Complexity | M |
| Estimated effort | 59 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
