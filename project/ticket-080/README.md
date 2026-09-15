# Ticket 080: Make repository-local Planfile configuration and external readback reconciliation deterministic

- **ID**: ticket-080
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: execute, test, push and protected merge,
requested by the owner on 2026-09-15.

## Goal and scope

The repository-local configuration CLI must not resolve an explicit project
path through a parent checkout. This ticket is intentionally limited to that
configuration isolation; the related schema and external readback repairs are
owned by separate active work.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [x] AC-02: Explicit `--project` configuration writes stay within that project.
- [ ] AC-03: Focused and full test suites pass; protected PR is merged at exact head.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
