# Ticket 173: Fix ambiguous local mapping on duplicate ticket IDs in planfile sync

- **ID**: ticket-173
- **Owner**: agent:Antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-28
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION ("wykonaj")

## Goal and scope

In `planfile/sync/operations.py`, `_find_local_ticket()` matches an external ticket against local tickets in all sprint sections (including historical sprints).
When a ticket exists in multiple sprints with the exact same local ID (e.g. carried over or archived across history files), `_find_local_ticket` threw `ValueError: ambiguous local mapping for remote ticket <id>`.

1. Deduplicate matching records by `local_id`. If all matching tickets share the same `local_id`, return the match (preferring `current`, then `backlog`, then the first match).
2. If multiple distinct `local_id`s match, prefer a match in `current` or `backlog` if exactly one is present.
3. Add regression tests in `tests/test_sync_legacy_operations.py`.

## Acceptance criteria

- [x] AC-01: `_find_local_ticket()` deduplicates by `local_id` when the same ticket exists across multiple history sprints.
- [x] AC-02: `_find_local_ticket()` prefers active/current sprint when resolving matches.
- [x] AC-03: Regression tests verify that duplicate mappings with the same local ID do not raise `ValueError`.
- [x] AC-04: Test suite passes with 0 errors.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
