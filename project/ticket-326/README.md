# Ticket 326: Support P0-P3 inbound priority aliases and quarantine invalid priority labels under isolate-conflicts

- **ID**: ticket-326
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-23

## Goal and scope

Map P0-P3 priority scale aliases (`p0` -> `critical`, `p1` -> `high`, `p2` -> `normal`, `p3` -> `low`) in `planfile.sync.priority.normalize_inbound_priority`, and allow `--isolate-conflicts` (`isolate_ticket_conflicts=True`) to quarantine per-ticket `inbound_priority_invalid` / `inbound_priority_conflict` errors without blocking unaffected tickets or advancing the default fail-closed path.

## Acceptance criteria

- [x] AC-01: `normalize_inbound_priority` maps `p0/p1/p2/p3` (case-insensitive) to `critical/high/normal/low`, rejects conflicting combinations, and raises the updated diagnostic message.
- [x] AC-02: `_is_isolatable_ticket_conflict` quarantines `inbound_priority_invalid` and `inbound_priority_conflict` only when `isolate_ticket_conflicts=True`, leaving default behavior fail-closed.
- [x] AC-03: Targeted tests in `tests/test_sync_legacy_operations.py` and `tests/test_sync_inbound_sdk_revision.py` plus ruff and governance checks pass.

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
