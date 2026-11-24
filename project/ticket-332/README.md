# Ticket 332: Skip resurrecting retired local tickets with own planfile deduplication-key during inbound sync

- **ID**: ticket-332
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-24

## Goal and scope

Prevent inbound `sync_from_external` from resurrecting retired local tickets as duplicate `GITHUB-N` entries when the remote issue carries this repository and Planfile store's own `<!-- planfile:deduplication-key=<repo>:<store_identity>:<local_id> -->` marker (addresses `semcod/planfile#474`).

## Acceptance criteria

- [x] AC-01: When `_find_local_ticket` finds no matching local ticket and the external ticket carries a `planfile:deduplication-key` (or `metadata.planfile_id` / `deduplication_key` / `dedupe_key`) matching both the active `sync_state.repository` and `sync_state.store_identity`, `_process_external_ticket` skips importing it instead of creating a duplicate `GITHUB-N` ticket.
- [x] AC-02: External tickets without a marker, or with a marker from a different repository or different `store_identity`, continue to import normally as `GITHUB-N`.
- [x] AC-03: Unit tests in `tests/test_sync_inbound_resilience.py` verify both skip and normal-import paths, and governance/lint checks pass.

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
