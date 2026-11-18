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
- [x] AC-03: Validate with private test stores and request independent source publication.

## Verification

Two private runs started with 1,245 tickets. One reproduced a committed write under SQLite contention. The other reproduced the observed change to the current sprint with an unchanged invalidation token. In each case the accepted base scanned the archive once. The candidate refreshed the 245 tickets in the changed sprint with zero full archive scans. The historical control and the updated ticket both matched the authoritative store.

The two stable-token regression cases failed on the first candidate and passed after this correction. The existing one-sprint concurrent rebuild test covers the fallback. Independent publication is tracked in PR #349.
