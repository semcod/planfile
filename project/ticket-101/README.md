# Ticket 101: Make legacy GitHub sync fail-closed with durable outcomes and readback

- **ID**: ticket-101
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested autonomous continuation,
repair, tests and protected publication of the Planfile synchronisation fixes.

## Goal and scope

Close the remaining legacy outbound synchronisation gap tracked by
`semcod/planfile#88`. Direct callers of `planfile.sync.operations.sync_to_external`
must use the same fail-closed batch path as the CLI, preserve successful
repository-bound mappings, and report a deterministic machine-readable result.
When a provider has committed a create but the response is lost, a unique
marker search may recover that issue; the client must never blindly create a
second issue. Provider readback is advisory and never substitutes for the
durable local receipt.

This ticket does not change credentials, hosted or local CI policy, inbound
comment transport, or the dirty primary checkout. It keeps the existing
receipt/state files and their repository binding; no live fault injection is
used in tests.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [ ] AC-02: The legacy operations API is fail-closed and raises the typed
  aggregate after saving successful mappings and receipts.
- [ ] AC-03: Results expose stable `created`, `reused`, `updated`, `failed`
  and `planned` ticket IDs without exposing provider error text or secrets.
- [ ] AC-04: A lost create response can be recovered by one unique marker
  match; ambiguous or unavailable search remains a failed/unknown outcome and
  never retries create automatically.
- [ ] AC-05: Focused offline regressions, full Python tests, Ruff, whitespace,
  managed governance and protected exact-head publication pass.

## Validation evidence

- `uv run --no-sync pytest -p no:wellmanifest_governance -q
  tests/test_sync_legacy_operations.py tests/test_sync_receipts.py
  tests/test_sync_failure_status.py tests/test_sync_scope.py
  tests/test_sync_routing.py` — 47 passed.
- `uv run --no-sync pytest -q` — 609 passed, 6 skipped, 1 existing warning.
- Ruff and `git diff --check` — passed.
- `./project/governance-check.sh --base origin/main --head HEAD --actor agent`
  — GOV-PASS.

Python 3.10 was not installed on this host; the second matrix leg remains a
protected CI/Validator responsibility. No live provider or credential was
used by these tests.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
