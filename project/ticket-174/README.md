# Ticket 174: Reconcile duplicate issues and serialize creation in GitHub sync

- **ID**: ticket-174
- **Owner**: agent:Antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-29
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION ("WYKONAJ KOLEJNO")

## Goal and scope

Resolves PLF-2707 / GitHub #261 in `planfile`:
1. **Deduplication key reconciliation**: When querying GitHub for existing issues by marker (`<!-- planfile:deduplication-key=... -->`), prioritize OPEN issues over CLOSED duplicates. If multiple issues share the deduplication key, detect and report duplicate collision rather than silently binding to an arbitrary closed issue or creating duplicates.
2. **Serialized creation**: Enforce a cross-process lock (`FileLock`) per repository and ticket during issue creation, eliminating race conditions between concurrent automated/manual workers.
3. **Atomic persistence**: In `sync_to_external()`, persist the canonical remote issue ID, receipt, and sync-state entry atomically per created ticket.
4. **Consistency check**: Implement `check_sync_consistency()` that flags ticket `sync.github` mappings disagreeing with `github.state.yaml` or pointing to missing/closed duplicates.
5. **Deterministic tests**: Add test coverage for concurrent create serialization, duplicate detection, and reconciliation.

## Acceptance criteria

- [x] AC-01: `_find_issue_by_markers()` prioritizes OPEN issues and detects duplicate collisions.
- [x] AC-02: Issue creation is serialized under a repository/ticket file lock.
- [x] AC-03: Remote issue ID, sync state, and receipts are recorded atomically.
- [x] AC-04: `check_sync_consistency()` flags state/ticket disagreements.
- [x] AC-05: Test suite passes with 0 failures and 0 warnings.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
