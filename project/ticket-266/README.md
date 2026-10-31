# Ticket266: Bounded indexed ticket discovery through Store and API

- **ID**: ticket-266
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-31

SESSION_EXECUTION_AUTHORIZATION: continue PLF-20292 under the accepted Heyasa/Planfile autonomy objective. Published ticket244 primitives are installed and verified, but have no Planfile Store/API caller. Source264/265 and Platform480 are independently merged and Native-qualified.

## Acceptance criteria

- [x] AC-01: Public SDK and HTTP provide bounded indexed identity/queue pages, preserving explicit history and waiting/retry semantics, without archive decoding or global counts.
- [x] AC-02: Cursor query/generation binding, strict freshness and concurrent page coherence hold; an unavailable index refuses without foreground rebuild or authority changes.
- [ ] AC-03: Affected checks, governance, independent source publication and installed/Native qualification pass; physical authoritative history migration remains separate.

## Validation

98 scoped discovery/index tests pass, including the 50,000-record routing benchmark and coherent concurrent-delete reads. Another 95 API/startup/legacy-state regression tests pass. Ruff and governance pass. Discovery opens SQLite with mode=ro, checks the current routing generation and indexes, and never initializes/upgrades a legacy projection or performs a global COUNT. The health capability advertises the new query. Independent publication and installed Native qualification remain pending.
