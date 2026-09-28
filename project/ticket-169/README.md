# Ticket 169: Reduce Planfile CLI startup cost for Koru ticket operations

- **ID**: ticket-169
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested work on dependencies delaying Koru tasks, with implementation and tests. Koru ticket331 is explicitly deferred; ticket332 belongs to Gemini. This dependency-side scope is disjoint from Planfile ticket168's group commands.

Planfile CLI currently imports and builds every command group for each `ticket` subprocess. Register only the ticket group for ordinary ticket entrypoint calls. Preserve the complete public Typer app, root help, other commands, option errors and shell completion. Do not change ticket lifecycle, storage, governance or retries.

## Acceptance criteria

- [x] AC-01: Public entrypoint ticket calls do not load unrelated groups; real temporary-project ticket operations retain semantics.
- [x] AC-02: Complete app/help, other commands, aliases and completion behavior stay compatible.
- [x] AC-03: Cold subprocess timings improve against the accepted base; focused tests and managed gate pass.
- [ ] AC-04: Protected exact-head publication and isolated runtime verification; no global dependency replacement.

## Validation

45 existing and new targeted tests passed; the additional real Bash completion test passed after correcting its Typer instruction fixture. This covers 46 distinct checks, including fresh subprocess import boundaries, real create/show/done lifecycle, root help/version, aliases, unknown options and full public app compatibility. Scoped Ruff and managed governance pass.

Five alternating cold-process samples per version on the same Python3.13 interpreter: base median2.147s, candidate1.740s (19.0% reduction; 1.23x speedup). Host load varied; this measures CLI ticket help startup, not total task execution or model latency. No paid requests and no production queue mutations were used.

AC-04 remains pending independently approved exact-head publication and runtime verification.
