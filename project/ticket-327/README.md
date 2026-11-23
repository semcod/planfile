# Ticket 327: Handle legacy tickets missing inner id and quarantine ambiguous sync mappings under isolate-conflicts

- **ID**: ticket-327
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-23

## Goal and scope

Handle legacy inbound ticket snapshots that lack an inner `id` field in `planfile.sync.operations` (`_freeze_observed_updated_at` and `_update_local_ticket`) without triggering `evidence_ticket_id_invalid`, while keeping CAS snapshot verification (`expected_snapshot`) intact and backfilling `id`. Also allow `--isolate-conflicts` (`isolate_ticket_conflicts=True`) to quarantine `ambiguous sync mapping` and `evidence_ticket_id_invalid` errors per ticket while preserving default fail-closed behavior.

## Acceptance criteria

- [x] AC-01: `_freeze_observed_updated_at` and `_update_local_ticket` handle legacy local tickets missing an inner `id`, backfill `id`, and update without raising `evidence_ticket_id_invalid`.
- [x] AC-02: `_process_external_ticket` and `_is_isolatable_ticket_conflict` quarantine `ambiguous sync mapping` and `evidence_ticket_id_invalid` only when `store is not None` and `isolate_ticket_conflicts=True`, keeping default behavior and legacy `store is None` filters fail-closed.
- [x] AC-03: Regression tests in `tests/test_sync_inbound_sdk_revision.py`, plus `tests/test_sync_selective_filter.py`, `ruff`, and governance checks pass.

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
| Estimated effort | 51 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
