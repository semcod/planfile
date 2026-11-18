# Ticket 287: Reconcile a bounded stale index before an archive rebuild

- **ID**: ticket-287
- **Owner**: agent:codex-autonomy-repair
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Scope

Continue PLF-27182 and semcod/planfile#313. Planfile issue discovery intermittently returns HTTP 503 while the SQLite index catches up. Reuse bounded reconciliation in background maintenance for a validated stored generation. Preserve the existing full-scan fallback and exact generation checks.

SESSION_EXECUTION_AUTHORIZATION: user approved this ticket's three implementation and test files, ticket metadata, and a maximum 120 minutes of source admission from activation. The production database has separate ownership.

## Acceptance criteria

- [x] AC-01: Reconcile a bounded changed sprint or journal without an archive scan and preserve deletion and ordering semantics.
- [x] AC-02: Fall back when metadata, schema, budgets or concurrent observations cannot confirm correctness.
- [ ] AC-03: Validate with private test stores and request independent source publication.

## Verification

On a private store of 1,245 tickets, a competing SQLite writer forced a durable update to be deferred. The accepted base scanned the archive once. The candidate refreshed the 245 tickets in the changed sprint, preserved the historical record, and restored indexed reads with zero full archive scans. The existing full-rebuild path still handles an unannounced YAML edit.

The 42 tests in the index repair module passed on Python 3.13, including two-process contention, malformed metadata, repair budgets, and source changes during reconciliation. Independent publication is tracked against the frozen Git head.
