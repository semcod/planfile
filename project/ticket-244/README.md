# Ticket 244: Add intent-scoped indexed ticket lookups without history scans

- **ID**: ticket-244
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-26

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requests intent-dependent queries for
tens of thousands of tickets and a separate database for closed tickets.
Parent request: Maskservice PLF-17353. Existing Coding Agent219/PR251 and
Planfile243 ownership remain preserved. Source lease acquired for codex-ticket244-20261026; maxActiveMinutes: 60.

This first slice adds indexed queue and external-identity lookup primitives in
sqlite_index.py. API/Store integration and physical history migration follow
under the owning integration scope after ticket243. Increasing page caps does
not satisfy the request. Preserve existing index callers and authoritative data.

## Acceptance criteria

- [x] AC-01: Exact ID and repository/issue lookup use indexed bounded reads;
  multiple issue revisions remain distinguishable, with no cross-repository matches.
- [x] AC-02: Queue selection uses executable state, queue and repository filters;
  blocked, waiting and retryable failures are not mistaken for closed work.
- [x] AC-03: Explicit history queries remain available; the execution path does
  not enumerate historical payloads or perform a global COUNT before selecting work.
- [x] AC-04: Benchmark at least 50,000 records, assert indexed query plans and
  bounded rows materialized; verify parity, missing IDs, reopen and pagination.
- [ ] AC-05: Obtain current fencing before source edits; run affected tests,
  governance and independently verified publication. Deployment is separate.

## Follow-on storage contract

Separate active.sqlite3 and history.sqlite3 behind the public store contract.
Keep a small global ID/external-identity locator. Migrate only confirmed terminal
records without pending work or live leases. Preserve IDs, evidence, references
and revisions. Copy, verify and durably journal before removing the active copy;
recover idempotently after interruption. Reopen through the same revision-checked
protocol. Do not assume a cross-database WAL transaction is atomic. History is
searched explicitly, while exact lookups may use its locator. YAML is currently
authoritative; changing that contract requires a versioned migration and rollback.

## Baseline evidence

A synthetic 50,000-record warm SQLite benchmark found a full scan for a global
status query (6.1582 ms), versus 0.0108 ms for scoped current work and 0.0033 ms
for a primary-key lookup. A separate 100-record active database took 0.0185 ms.
These are microbenchmarks, not end-to-end SLA claims. Machine-local raw evidence
is in the owning repository's ignored receipts for this ticket. No production
record was moved, deleted or reclassified.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

## Verification

38 scoped SQLite/index regression tests passed, including 50,000-record query
plans, bounded payload reads, legacy projection upgrade, reopen/delete, identity
isolation and cursor ties. Ruff and git diff --check pass. Store/API wiring and
physical history separation are not implemented in this slice.
