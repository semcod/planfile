# Ticket 304: Preserve index correctness after shard rotation and locator removal

- **ID**: ticket-304
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION is the request to continue, merge and test the Planfile recovery.
Continue from merged PR #440 at beb9c46. Correct stored-baseline repair for a removed
current shard and when an unrelated locator removal changes the canonical historical copy.
Use the protected publication process for this candidate after verification.

## Acceptance criteria

- [x] AC-01 Recover both ready queues after a proven current shard rotation without a full scan.
- [x] AC-02 Refuse incremental publication when a removed shard has an unaccounted ticket.
- [x] AC-03 Rebuild on a locator removal that changes canonical selection across unchanged sprints.
- [x] AC-04 Preserve discovery generation fencing and pass recovery and integration tests.

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
