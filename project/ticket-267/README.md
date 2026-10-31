# Ticket267: Bounded index convergence across locator changes

- **ID**: ticket-267
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-31

SESSION_EXECUTION_AUTHORIZATION: continue existing PLF-20292/parent20347 after independently merged Willman449/PR454. Real installed discovery correctly defers503 ticket_index_stale. Read-only Native observations show current/history source changes plus locator drift; existing finalizer refuses all locator drift. This is a bounded source/runtime continuation, not permission to weaken freshness, delete locks or migrate canonical authority.

## Acceptance criteria

- [x] AC-01: Independent writer rotation/locator changes during rebuild converge in one bounded finalization with canonical precedence and identity coverage preserved, for flat/sharded stores.
- [x] AC-02: Missing/ambiguous locator baseline, races and byte/ticket/time bounds fail closed; unchanged historical payloads are not scanned unnecessarily.
- [ ] AC-03: Focused regression checks, governance, independent source publication, installed artifact and separately fenced Native behavior are verified and reported distinctly.

## Validation and deployment boundary

The exact unmodified accepted base fails all four independent relocation regressions by requiring two scans; the candidate converges in one scan.123 focused repair/discovery/SQLite regressions pass (49.49seconds). Tests include flat/sharded relocation, locator-only duplicate precedence and mapping removal, bounded/invalid/racing locator snapshots, and unchanged byte/ticket/time and external-editor refusal. Ruff passes for all three implementation/test files; managed governance passes. Hostguard/Fixos classify current CPU pressure; no foreign process, lease, lock or IDE is terminated.

Independent publication, installed artifact and actual Native sustained-writer readback remain separate AC-03 evidence. The existing Willman430/PLF20340 host adapter dependency remains open; source publication alone cannot prove fleet autonomy or physical active/history authority migration.
