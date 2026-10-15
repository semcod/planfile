# Ticket 216: Avoid SQLite projection rebuild under deduplication lock

- **ID**: ticket-216
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Planfile**: PLF-18410

## Authorization

SESSION_EXECUTION_AUTHORIZATION: continue repairs, tests, protected merges. Previous ticket215 is merged/deployed; this bounded followup addresses first reuse latency. A stale/missing SQLite projection currently triggers full archive reconstruction while holding mutation_lock.

## Acceptance criteria

- AC-01: Dedupe reuse must not rebuild a stale or missing SQLite projection under the mutation lock.
- AC-02: Current and archived tickets, occurrence notes and terminal key release retain authoritative semantics; normal index maintenance remains available.
- AC-03: Regression tests, full suite, governance and protected exact-head review pass.

## Validation

Deterministic stale/missing-index tests and full pytest; isolated snapshot measurement if useful. Never mutate production tickets for benchmarking.

## Local results

All eight new regression cases failed before the change because dedupe invoked full projection repair. After the change: 45 focused tests passed; full suite 1273 passed, 6 skipped (110.94s); Ruff and governance passed. Isolated HTTP measurement running; protected CI and independent Validator required.
