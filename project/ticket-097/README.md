# Ticket 097: Automate GitHub synchronization for reusable CI workflows

- **ID**: ticket-097
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested implementation,
validation, publication and protected merge of automatic Planfile/GitHub
synchronization across the participating repositories.

## Goal and scope

Add an explicit repository override and a managed-Issue import boundary to the
GitHub sync command. The reusable workflow and release files are delivered by
separate infrastructure and integration changes; this ticket owns only the
application sync path and its offline regressions.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [ ] AC-02: `sync github --repo ...` binds the operation to the requested
  repository even when no local GitHub config exists.
- [ ] AC-03: `--managed-only` imports only Issues carrying the Planfile
  management labels and does not alter the outbound ticket selection.
- [ ] AC-04: Focused and full offline tests, lint, governance and exact-head
  publication checks pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

The caller supplies the repository identity in CI from `GITHUB_REPOSITORY`.
Remote filtering is passed through the backend protocol, so unrelated Issues
are never imported into a local Planfile store.
