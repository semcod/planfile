# Ticket 331: Classify typer.Exit(2) deferred outbound conflicts separately from hard failures in planfile sync fleet

- **ID**: ticket-331
- **Owner**: agent:antigravity (SESSION_EXECUTION_AUTHORIZATION from user request)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-24

## Goal and scope

When `planfile sync fleet --direction both` (or `--direction to`) runs against
repositories that have mapped tickets deferred due to lifecycle conflicts,
`sync_integration` exits with `typer.Exit(2)` after completing safe inbound and
new-ticket outbound sync. `sync_fleet` currently counts `typer.Exit(2)` under
`stats["failed"]` as `Sync error for <repo>: 2`, masking real failures.

Classify `typer.Exit(2)` / `SystemExit(2)` for `to` and `both` directions under
a dedicated `stats["deferred"]` counter (`status: "deferred"`) and display
`Deferred:` in the fleet summary table, while keeping `exit(1)` and inbound
`exit(2)` as hard failures.

## Acceptance criteria

- [x] AC-01: `sync_fleet` tracks `stats["deferred"]` and records `status: "deferred"` for `typer.Exit(2)`/`SystemExit(2)` when `direction in {"to", "both"}`.
- [x] AC-02: `typer.Exit(1)` and `direction="from"` `typer.Exit(2)` remain counted in `stats["failed"]`.
- [x] AC-03: `fleet_cmd` renders `⚠ deferred` in the table and `Deferred: N` in the summary line.
- [x] AC-04: Unit tests in `tests/test_sync_fleet.py` pass with 0 ruff errors and `GOV-PASS`.
