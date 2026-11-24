# Ticket 329: Enable isolate-conflicts by default and bounded inbound transient retry in planfile sync fleet

- **ID**: ticket-329
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-24

## Goal and scope

Enable `isolate_ticket_conflicts=True` by default in `sync_fleet` and expose `--isolate-conflicts/--no-isolate-conflicts` on `planfile sync fleet` so automated scheduled fleet runs quarantine per-ticket inbound conflicts instead of aborting the repository cursor. Add a bounded 1-retry guard for transient DNS/transport failures exclusively on read-only `direction="from"` fleet runs, never retrying quota/permission errors (`403`/`429`) or mutating `direction="to"`/`"both"` runs.

## Acceptance criteria

- [x] AC-01: `sync_fleet` defaults `isolate_ticket_conflicts=True` and `planfile sync fleet` exposes `--isolate-conflicts/--no-isolate-conflicts`.
- [x] AC-02: `sync_fleet(..., direction="from")` retries transient DNS/socket errors once cleanly, while skipping retries for `403`/`429`, `SyncDeadlineExceededError`, and `direction in {"to", "both"}`.
- [x] AC-03: Unit tests in `tests/test_fleet_sync.py`, `tests/test_sync_fleet.py`, `ruff`, and governance checks pass.

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
