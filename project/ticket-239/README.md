# Ticket 239: Keep lifecycle writes independent of background index repair

- **ID**: ticket-239
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-24

## Authorization and accepted request

SESSION_EXECUTION_AUTHORIZATION: continue autonomous diagnosis, repair, testing and protected publication with Willman and Subactor. This bounded dependency repair follows Heyasa ticket-053 (PR 51 merged and activated). Runtime canary PLF-19820 executed its read-only query but could not commit completion because background Planfile index rebuilding held the authoritative store lock. No second human confirmation is pending.

## Goal and scope

Prevent disposable SQLite projection repair from serializing authoritative lifecycle writes. Use exact durable ticket fallback on ready/complete/fail reads when the index is stale. Reuse the existing cross-process index lock and source-signature validation. Preserve API contracts, CAS conflict handling, terminal immutability, retry counters and receipts. Source ownership is disjoint from active ticket-238 synchronization paths.

## Acceptance criteria

- [x] AC-01: A deliberately stalled background index rebuild does not hold the YAML mutation lock; a concurrent lifecycle write commits before repair resumes.
- [x] AC-02: Source changes during repair are detected; stale snapshots are never considered current and concurrent repairs coalesce.
- [x] AC-03: Ready, complete and fail use exact durable fallback without synchronous full projection rebuild, preserving terminal/CAS/attempt semantics.
- [ ] AC-04: Focused and required repository checks pass, the immutable source head is released before native OneDev and independent protected Validator publication.

## Delivery boundary

Implementation: planfile/api/server.py, planfile/__init__.py and two scoped test modules. Runtime activation follows trusted merge and a separate exact deployment reservation. Do not clear locks, reset attempts, kill unknown owners or rewrite other worktrees.

Existing checks in the two touched test modules are normalized: remove one identical overwritten test and an unused binding; compare API description with the created ticket including the native advisory radar. Lifecycle readback permits the existing automatic move to history while verifying all other fields.

Validation: 90 focused tests passed (SQLite repair, lifecycle, lock timeouts and store concurrency), managed governance 0 errors/0 warnings and scoped Ruff pass. Red reproduction: seven new cases failed before the fix. Independent OneDev and Validator publication remains required. Willman read-only task e67d6a2069fa48fd8fb7c16dd9de9cee was accepted but resource-throttled; it is not counted as completed validation.
