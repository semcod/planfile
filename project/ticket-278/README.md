# Ticket 278: Fleet sync and inbound GitHub sync on ticket creation

- **ID**: ticket-278
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-11-04

## Goal and scope

Implement autonomous and cyclic synchronization from GitHub to Planfile:
1. Fleet sync across repositories in `~/github/*/*` with 6-hour systemd user timer integration, rate limit protection, and filtering of transient crash/incident noise (such as browser autocontrol dumps).
2. Automatic inbound GitHub inspection and synchronization before creating local tickets in `planfile ticket create` to ensure the local store is up-to-date with remote issues and avoid duplicate allocations.

## Acceptance criteria

- [x] AC-01: Incident noise filter (`is_incident_noise`) excludes transient runtime crashes and degradation reports (`[autocontrol-...]`, `[computer-use:...]`, `incident-report`).
- [x] AC-02: `planfile sync fleet` discovers repositories configured with GitHub and performs bounded inbound synchronization.
- [x] AC-03: `planfile sync fleet --install-timer` generates, registers, and starts a 6-hour systemd user timer (`planfile-fleet-sync.timer` & `planfile-fleet-sync.service`).
- [x] AC-04: `planfile ticket create` inspects and synchronizes remote GitHub issues into local Planfile prior to creating new tickets when remote integration is configured, with `--inbound-sync / --no-inbound-sync` control and graceful failure handling.
- [x] AC-05: Unit and integration tests in `tests/test_fleet_sync.py` and `tests/test_ticket_create_inbound_sync.py` pass without regression.

## Implementation details

- `planfile/sync/operations.py`:
  - Added `is_incident_noise(ext_ticket)` detecting transient crash logs and degradation reports.
  - Added `exclude_incident_noise: bool = False` to `sync_from_external`.
- `planfile/cli/groups/sync/core.py`:
  - Propagated `exclude_incident_noise` through `_execute_sync_with_progress` and `sync_integration`.
- `planfile/cli/groups/sync/fleet.py`:
  - Created fleet synchronization module: `discover_fleet_repositories`, `sync_fleet`, `install_fleet_systemd_timer`, `uninstall_fleet_systemd_timer`, `status_fleet_systemd_timer`, and `fleet_cmd`.
- `planfile/cli/groups/sync/commands.py` & `planfile/cli/groups/sync/__init__.py`:
  - Registered `fleet_cmd` under `planfile sync fleet`.
- `planfile/cli/groups/ticket/commands.py`:
  - Added `inbound_sync` option and `_inbound_sync_before_create` helper to reconcile remote issues before local ticket creation.
- `tests/test_fleet_sync.py`:
  - Added comprehensive tests for noise detection, repo discovery, systemd unit generation, and CLI dry-run.
- `tests/test_ticket_create_inbound_sync.py`:
  - Added tests for automatic inbound synchronization, `--no-inbound-sync` override, and error tolerance.
