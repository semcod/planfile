# Ticket 315: Fix fleet repository discovery across org dirs and reject GitHub PR mappings at write time

- **ID**: ticket-315
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21
- **Authorization**: `SESSION_EXECUTION_AUTHORIZATION` (user request to investigate Planfile-to-GitHub synchronization, fix defects found, and enable governed fleet sync & execution across projects).

## Goal and scope

1. Fix `discover_fleet_repositories()` in `planfile/cli/groups/sync/fleet.py`: stop halting BFS at depth-1 non-Git organization directories that contain `.planfile/` (which previously hid 169 real GitHub-configured repositories under `~/github/*/*`), drop non-Git container dirs shadowed by real child repos, catch `SystemExit`/`typer.Exit` per repo, add `--timeout` / `--max-projects`, and add `flock` concurrency protection to generated systemd service units.
2. Fix `discover_planfile_repositories()` in `planfile/reconcile.py` with the same non-Git container descent rule so `planfile executable-queue --fleet` and `planfile reconcile --fleet` discover all real Git repositories instead of stopping at org directories.
3. Reject GitHub Pull Request URLs (`.../pull/...`) at write time in `planfile/sync/operations.py` (`_record_backend_ref`, `_update_local_ticket`, `_import_new_ticket`) per `docs/analysis/planfile-github-sync-fleet-audit-2026-11-21.md`.
4. Add unit tests in `tests/test_fleet_sync.py` and `tests/test_executable_queue.py`.

## Acceptance criteria

- [x] AC-01: `discover_fleet_repositories()` descends through non-Git org directories with `.planfile/` and discovers child GitHub repositories.
- [x] AC-02: `discover_planfile_repositories()` descends through non-Git org directories with `.planfile/` so `fleet_executable_queue()` scans child repositories instead of stopping at org containers.
- [x] AC-03: GitHub `/pull/` URLs are rejected at write time in `planfile/sync/operations.py`.
- [x] AC-04: `ruff check`, targeted pytest suites, and `./project/governance-check.sh --base origin/main` pass.
