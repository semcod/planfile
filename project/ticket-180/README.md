# Ticket 180: Preserve non-object ticket results

- **ID**: ticket-180
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION

SESSION_EXECUTION_AUTHORIZATION: continuing requested Planfile repairs and independent publication. Reproduced while closing Search deployment STARTER-032: valid result string caused ticket to disappear from readers.

- [x] AC-01: Any-valued results remain readable across YAML/sharded and index/source paths, including guarded updates.
- [x] AC-02: Evidence appends still reject non-object results without changing them; existing object evidence remains functional.
- [ ] AC-03: Focused regressions and required protected checks pass; independent publication binds exact head.

## Validation

Regression-first: 7 failed and 7 passed against immutable base 643585e. Final affected store/index/concurrency/evidence suites: 78 passed, governance 0 errors and 0 warnings. Valid scalar/list values survive indexed/source and YAML/sharded reads and timestamp-guarded updates. Object-only evidence append still rejects scalar results without making the ticket unreadable; object evidence preserves idempotency. PLF-101 owns this observed repair; required protected matrix and independent publication remain pending.
