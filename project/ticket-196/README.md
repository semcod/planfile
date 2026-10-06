# Ticket 196: Reject PR marker collisions and protect issue identities in GitHub sync

- **ID**: ticket-196
- **Owner**: gemini
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Prevent GitHub sync from mutating or mapping Pull Requests when syncing tickets. Enforce that `update_ticket`, `create_ticket`, and marker lookups reject pull requests, ensuring issue identities are preserved and PR collisions fail closed.

## Acceptance criteria

- [x] AC-01: Reject PR mappings in `_update_ticket` by asserting the target is an issue and not a pull request.
- [x] AC-02: Prevent `_create_ticket` from returning or caching pull request references.
- [x] AC-03: Add comprehensive regression tests for `update_ticket` and `create_ticket` with PR targets.
- [x] AC-04: Ensure all tests pass and governance checks exit 0.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
