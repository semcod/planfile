# Ticket 272: Reconcile renamed GitHub repositories read-only during sync --dry-run

- **ID**: ticket-272
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-02

## Goal and scope

Reconcile renamed GitHub repositories (`owner/old` -> `owner/new`, e.g. `paxlet-com/heyasa` -> `heyasa/heyasa`) in read-only mode (`persist=False`) during `sync_from_external(..., dry_run=True)` and `sync_to_external(..., dry_run=True)` when `github.state.yaml` still binds to the pre-rename repository route or carries verified aliases, without rewriting `github.state.yaml` on disk or performing network queries when repository bindings already match.

SESSION_EXECUTION_AUTHORIZATION: User authorized autonomous execution and testing of all concrete project planfile tickets (`PLF-20366`).

## Acceptance criteria

- [x] AC-01: `sync_from_external(..., dry_run=True)` and `sync_to_external(..., dry_run=True)` succeed against a renamed GitHub repository (`owner/new`) when `github.state.yaml` still records `owner/old` with matching numeric `repository_id`, leaving `github.state.yaml` bytes unchanged on disk.
- [x] AC-02: Mismatched numeric `repository_id` or unrelated repositories continue to fail closed with `SyncStateRepositoryMismatch` during `--dry-run`.
- [x] AC-03: Direct `SyncState.from_backend(..., dry_run=True)` and non-renamed `--dry-run` sync runs perform zero extra provider identity queries.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
