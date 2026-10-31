# Ticket265: Legacy dependency-wait read compatibility

- **ID**: ticket-265
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-31

SESSION_EXECUTION_AUTHORIZATION: continue the accepted Planfile/Heyasa autonomy repair. The full ticket264 canary exposed two preexisting waiting_dependency rows omitted by the live and published models. Preserve their waits and dependencies in read projection, then qualify a combined Native candidate after independent source publication.

## Acceptance criteria

- [x] AC-01: Legacy dependency-wait rows remain visible in point/list/API/index reads with no source rewrite, invented executor, readiness promotion or command-enum expansion.
- [ ] AC-02: Affected checks, governance and independent source publication pass; Native activation remains a separate qualified effect.

The private read-projection revision invalidates a preexisting current SQLite index even when authoritative source bytes are unchanged. This is necessary for an old index that omitted the legacy rows to gain them after the parser repair. The same ticket scope was reconciled through an explicit owned-writer handoff from fence451 to452, adding only core/store.py.

Validation:62 affected tests passed, including point/list/API/index visibility, preserved queue/dependency waits, strict command validation, conflicting terminal states, automatic regeneration of an old-generation index and concurrent-writer convergence. The adopted governance gate passed with0errors/0warnings; changed Python files passed Ruff. Protected publication and installed/Native qualification remain separate delivery steps.
