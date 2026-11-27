# Ticket 338: Add write-free --dry-run to ticket create, warn on --sync-dry-run, and notify on unsynced remote updates

- **ID**: ticket-338
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-27

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: User requested continuation, repair, and protected merge ("kontynuuj") for `semcod/planfile#476`. This bounded application slice operates only inside `planfile/cli/groups/ticket/commands.py` and `tests/test_ticket_dry_run_and_sync_notice_cli.py`.

1. Add a write-free `--dry-run` flag to `ticket create` that runs before `Planfile.auto_discover()`, leaves `.planfile/` completely untouched (same directory tree hash and unchanged `next_id`, or creates no `.planfile/` in an uninitialized repo), and clarifies `--sync-dry-run` with an explicit warning when a local ticket was written.
2. Harmonize `--sync/--no-sync` defaults on `ticket update`, `ticket delete`, and `ticket bulk-update` so local-only mutations emit a clear notice whenever a ticket is linked to remote integrations unless `--no-sync` or `--sync` is passed.

## Acceptance criteria

- [x] AC-01: `ticket create --dry-run` leaves an initialized `.planfile/` tree hash and `next_id` identical and creates no `.planfile/` directory in an uninitialized Git repository while skipping inbound/outbound sync.
- [x] AC-02: `ticket create --sync-dry-run` preserves existing sync-preview behavior while emitting an explicit warning that the local ticket was written and pointing to `--dry-run`.
- [x] AC-03: `ticket update`, `ticket delete`, and `ticket bulk-update` warn clearly when a remote-linked ticket is modified locally without `--sync` and stay silent when `--no-sync`, `--sync`, or local-only tickets are used.
- [ ] AC-04: Targeted pytest suites, Ruff (if available), `./project/governance-check.sh --base origin/main`, `wellman check`, GitHub CI checks, `onedev/local-verify`, and independent `app/ifuri-validator-agent` approval/merge pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
