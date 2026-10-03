# Ticket 178: Filter remote tickets before mapping lookup during selective sync

- **ID**: ticket-178
- **Owner**: antigravity / user-authorized maintenance
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-03

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested:
"kontynuuj wykonywanie zaleglych zmian i scalaj projekty w maskservice/*" -> "kontynuuj"

When executing selective sync (e.g. `planfile sync github --direction from --ticket <ID>`), planfile currently fetches external tickets and calls `_find_local_ticket(...)` for every fetched remote issue before checking if the ticket matches the specified `--ticket` filter. If any unrelated remote ticket has an ambiguous local mapping in `sync_state` (such as historical duplicate issues like #141), `sync_state.get_local_id(...)` raises `ValueError: ambiguous sync mapping for remote ticket 141`, failing the entire selective sync operation even when the user only asked for a distinct ticket (e.g. `PLF-2787`).

Filter remote tickets before reverse-mapping lookup by pre-resolving candidate remote IDs from the requested ticket IDs and mapping references. Only tickets matching the filter will trigger mapping lookup. If the user explicitly requests an ambiguous ticket, fail closed as expected.

## Acceptance criteria

- [x] AC-01: Scope is approved by user execution authorization.
- [x] AC-02: Derive candidate remote IDs before calling `_find_local_ticket` in inbound sync when `--ticket` is specified.
- [x] AC-03: Skip non-matching external tickets before invoking `_find_local_ticket`.
- [x] AC-04: If an explicitly requested ticket has an ambiguous mapping, preserve fail-closed behavior.
- [x] AC-05: Unit tests verify selective sync filters without triggering ValueError on unrelated ambiguous tickets.
- [x] AC-06: Pinned governance checks pass.

## Evidence

Implemented `_resolve_selected_remote_ids` in `planfile/sync/operations.py` to precompute candidate remote IDs from `ticket_ids`, `sections`, and `sync_state`. Updated `_process_external_ticket` to skip non-matching remote tickets before calling `_find_local_ticket`. Preserved fail-closed behavior when an ambiguous ticket is explicitly requested. Added 4 unit tests in `tests/test_sync_selective_filter.py`. Tested live reproduction in `c2004`: `planfile sync github --direction from --ticket PLF-2787 --dry-run` successfully completed without triggering ValueError on #141, while `planfile sync github --direction from --ticket 141 --dry-run` properly failed closed with ValueError. All 140 sync tests and pinned `./project/governance-check.sh` pass with 0 errors and 0 warnings.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
