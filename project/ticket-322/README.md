# Ticket 322: Add --direction (from/to/both) support to planfile sync fleet

- **ID**: ticket-322
- **Owner**: agent:antigravity (SESSION_EXECUTION_AUTHORIZATION from user request)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-23

## Goal and scope

`planfile sync fleet` previously hardcoded `direction="from"` (inbound-only),
preventing scheduled fleet synchronization from pushing local `.planfile/`
completions/updates back to GitHub. Add `--direction` (`from` | `to` | `both`,
default `from` for backwards compatibility) to `sync_fleet` and `fleet_cmd`
with strict validation.

## Acceptance criteria

- [x] AC-01: `sync_fleet(..., direction=...)` validates `from`/`to`/`both` and forwards `direction` to `sync_integration("github", ...)`.
- [x] AC-02: `planfile sync fleet --direction both` is exposed on the CLI.
- [x] AC-03: Unit tests in `tests/test_sync_fleet.py` and existing `tests/test_fleet_sync.py` pass alongside `./project/governance-check.sh`.
