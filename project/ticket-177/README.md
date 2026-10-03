# Ticket 177: Auto-sync tickets to GitHub on creation when integration is configured

- **ID**: ticket-177
- **Owner**: antigravity / user-authorized maintenance
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-03

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested:
"czy po utworzeniu ticketu planfile sam robi sycnhronizacje z github automatycznie? jesli nie to zaimplemeutuj w planfile, zrob pulbikacje z goal -a i  prace i kontynuuj, scalaj"

When creating a ticket via `planfile ticket create`, if remote integrations (such as GitHub) are configured for the repository or specified, planfile should automatically attach the configured integration(s) and synchronize the created ticket outbound (`to`) unless `--no-sync` is explicitly specified. Support `--sync/--no-sync` flag in `ticket_create`. Ensure auto-sync is safe, tested, and publication is run with `goal -a`.

## Acceptance criteria

- [x] AC-01: Scope is approved by user execution authorization.
- [x] AC-02: `ticket_create` automatically detects configured remote integrations (e.g. GitHub) and auto-syncs the new ticket outbound unless `--no-sync` is passed.
- [x] AC-03: `ticket_create` supports explicit `--sync` and `--no-sync` flags (`typer.Option(None, "--sync/--no-sync")`).
- [x] AC-04: Unit and integration tests verify the auto-sync behavior upon ticket creation.
- [x] AC-05: Pinned governance checks pass.

## Evidence

Updated `ticket_create` in `planfile/cli/groups/ticket/commands.py` with `sync: bool | None = typer.Option(None, "--sync/--no-sync", ...)`. Discovers configured valid remote integrations via `IntegrationConfig`. When remote integrations (e.g. GitHub) are configured, auto-syncs outbound by default unless `--no-sync` is passed, or if `-i` is explicitly specified. Resiliently handles implicit auto-sync failure by printing a warning and retaining the local ticket. Added unit test suite in `tests/test_ticket_create_auto_sync.py` (6 tests passing). Pinned governance checks pass with 0 errors and 0 warnings.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
