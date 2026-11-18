# Ticket 291: Bound and atomicize API dependency DAG validation

- **ID**: ticket-291
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: user requested "wykonaj zalegle zadania https://github.com/semcod/planfile/issues" and "kontynuuj,scalaj"; resolves semcod/planfile#328 (PLF-21690) with protected Validator publication.

## Goal and scope

Eliminate unbounded `list(pf.list_tickets(sprint="all"))` scans in `_validate_api_dag_relations` (`planfile/api/server.py`) by querying an indexed edge snapshot (`SQLiteTicketIndex.dag_snapshot` in `planfile/core/sqlite_index.py`) without reading archived descriptions or artifacts, keeping validation and mutation inside a single non-reentrant `mutation_lock` / `deduplication_lock` snapshot, enforcing an explicit bounded fallback or typed retryable `503` refusal (`dag_validation_index_unavailable`) when the index is missing/stale, and surfacing distinct `dag_validation`, `canonical_write`, and `derived_index_degraded` diagnostic stages while preserving idempotency/CAS readback.

## Acceptance criteria

- [x] AC-01: Single DAG-edge API mutations validate acyclicity and references via indexed edge projections without calling `pf.list_tickets(sprint="all")` or reading archived ticket descriptions/artifacts.
- [x] AC-02: Concurrent opposing edge mutations (`A->B` and `B->A`) execute atomically under one store lock against the same committed snapshot so at most one succeeds and the persisted graph remains acyclic.
- [x] AC-03: Missing or stale SQLite index uses bounded incremental repair and an explicit byte-bounded fallback on small stores, or returns typed retryable `503` (`dag_validation_index_unavailable`) on oversized stores without disabling cycle checks.
- [x] AC-04: Post-commit timeouts and retries resolve via idempotency `dedupe_key` / `expected_updated_at` CAS readback, and stage headers/payloads distinguish `dag_validation`, `canonical_write`, and `derived_index_degraded`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
