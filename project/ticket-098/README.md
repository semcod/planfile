# Ticket 098: Provide reusable GitHub Actions workflow for Planfile sync

- **ID**: ticket-098
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested implementation,
validation, publication and protected merge of automatic Planfile/GitHub
synchronization across the participating repositories.

## Goal and scope

Provide a reusable GitHub Actions workflow that checks out the calling
repository, installs a pinned Planfile release and runs repository-bound,
managed-only reconciliation. Provide a caller template for rollout to every
repository with a local `.planfile` store.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [ ] AC-02: The reusable workflow grants only read access to contents and
  write access to Issues, and uses the calling repository identity.
- [ ] AC-03: The caller template runs hourly, on demand, and after Planfile
  source changes without overlapping runs.
- [ ] AC-04: Workflow YAML, governance and package integration checks pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
