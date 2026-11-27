# Ticket 339: Prepare current sprint data outside the index repair writer lock

- **ID**: ticket-339
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-27

## Goal and scope

Planfile #403 tracks stale queue reads and writer-lock contention during SQLite index repair. Prepare the changed current sprint outside the writer lock and revalidate its generation before using it.

## Acceptance criteria

- [x] AC-01: Read changed current YAML and sharded sprint files while the writer lock stays available.
- [x] AC-02: Reject outdated prepared records when a concurrent write changes the current sprint.

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
