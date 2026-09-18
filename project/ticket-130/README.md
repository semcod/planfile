# Ticket 130: Sync outbound never maps a ticket onto a pull request or persists a failed create

- **ID**: ticket-130
- **Owner**: agent:claude-code
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

SESSION_EXECUTION_AUTHORIZATION: user asked to work through the open sync
correctness backlog for this project ("zajmij się nimi") in an earlier turn
of this session; this ticket and its implementation are that authorized
work. Addresses GitHub issue semcod/planfile#126.

## Goal and scope

Issue #126 reports `planfile sync github --direction to` printing
`✓ Created: PLF-003 → 19` while creating nothing — `19` was an existing,
unrelated, merged pull request. The bogus `ticket_map` entry it produced is
the dangerous part: `semcod/monag#29` documents a repository having to
revert its Planfile store after hourly reconciliation tried to update that
pull request as an issue and failed every run.

Static review of the current `main` found the real code paths already
correctly exclude pull requests from dedup matching (`_find_issue_by_markers`)
and recovery search (`_search_tickets`), so this exact reproduction may be
from an earlier version of this code (the issue is filed against 0.1.126).
Rather than guess at the exact historical collision, this ticket closes the
structural gap that would let *any* future variant of this class of bug
(a create call returning an id this code cannot actually vouch for) turn
into a false "Created" report and a persisted bad mapping:

1. **`GitHubBackend._get_ticket`** (`planfile/sync/github.py`) now raises
   when the resolved GitHub number is a pull request rather than an issue.
   `GET /repos/{owner}/{repo}/issues/{number}` answers for both, so any
   caller resolving a ticket ref through this path — readback verification,
   `_recover_lost_create`'s search — previously had no way to reject a PR
   number specifically.
2. **The create path in `planfile/sync/outbound.py`** verified the readback
   *after* already recording the (unverified) reference on the ticket and
   printing "✓ Created" — a rejection at that point left the misleading
   record and the "Created" message in place even though the exception
   correctly failed the ticket overall. Reordered so `_create_new_ticket`
   returns the id/ref without recording or announcing anything;
   the caller now verifies first and only records + announces success once
   verification passes (or is unavailable on the backend, preserving the
   prior "trust the create response" behaviour for backends without
   `get_ticket`).
3. **The failure handler** in the same loop now pops any `ticket_map` entry
   a rejected attempt set before re-raising reached it, so a verified-bad id
   is never written to `.planfile/sync/*.state.yaml` by `save_sync`, even
   though it still appears on that ticket's `failed` receipt for diagnosis.

The secondary observation in #126 (a duplicate `priority: high` label on
`PLF-001`) was checked and is already fixed on `main`: `_prepare_labels`
already filters legacy `priority: ` labels and de-duplicates before
returning — not touched here.

## Acceptance criteria

- [x] AC-01: `GitHubBackend._get_ticket`/`get_ticket` raises when the
      resolved number belongs to a pull request.
- [x] AC-02: A create whose readback verification rejects the result is
      reported as failed, not `✓ Created`, and its ticket does not gain a
      `sync.github` reference.
- [x] AC-03: A rejected create's id is not present in `.planfile/sync/*.state.yaml`
      after the run (not left in `ticket_map` for `save_sync`).
- [x] AC-04: Existing sync test suites (`test_sync_failure_status.py`,
      `test_sync_legacy_operations.py`, `test_sync_receipts.py`,
      `test_sync_scope.py`, `test_github_deduplication.py`,
      `test_github_sync_preserves_issue.py`) still pass — the "no verifier
      available" path behaves exactly as before.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
