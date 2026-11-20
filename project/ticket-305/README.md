# Ticket 305: Skip non-locator archive and backlog sprints in `_has_unmapped_earlier_copy` during incremental index repair

- **ID**: ticket-305
- **Owner**: agent:antigravity (SESSION_EXECUTION_AUTHORIZATION)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

In production Planfile stores containing `backlog.yaml` and legacy `archive-YYYY-MM.yaml` sprints (55+ MB, never recorded in `history-locations.yaml`), `_has_unmapped_earlier_copy()` treats every unmapped `backlog`/`archive-*` ticket as a potential removed locator entry and reads untouched multi-megabyte archives through `tickets(sprint)`, blowing `MAX_REPAIR_BYTES` (32 MiB) and forcing `reconcile_index()` to return `None` on every daily archive move. Restrict `_has_unmapped_earlier_copy()` to locator-eligible sprints (`history-*` or sprints referenced in `locations.values()`), preserving full rebuild fallback when a real history locator entry is removed.

## Acceptance criteria

- [x] AC-01: `_has_unmapped_earlier_copy()` ignores non-locator sprints (`backlog`, `archive-*`, custom queues) that are neither `history-*` nor referenced by `history-locations.yaml`, so incremental archive-move repair succeeds without opening untouched legacy archives.
- [x] AC-02: Existing locator-removal precedence safety (`test_background_rebuilds_after_unrelated_locator_removal` and all `tests/test_index_repair.py` + `tests/test_ticket_discovery.py` tests) continues to pass.
- [x] AC-03: `./project/governance-check.sh --base origin/main` passes with zero errors.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
