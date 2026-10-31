# Ticket264: Concurrent index convergence

- **ID**: ticket-264
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-31

SESSION_EXECUTION_AUTHORIZATION: continue existing PLF-21260 under the authorized Heyasa autonomy repair and independent publication. YAML/evidence remain canonical; no lock deletion, live owner takeover, restart or active/history migration is implied.

## Acceptance criteria

- [x] AC-01: A full rebuild converges with independent concurrent canonical writes; bounded final reconciliation preserves exact payloads and fail-closed freshness.
- [ ] AC-02: Affected verification, governance and protected independent publication pass; native qualification is separate evidence.

Contract correction after GOV-ARCHITECTURE-001: the derived projection is component-local cache state, using the adopted typed ownership record. No business schema or authoritative data migration is part of this application slice.

Validation: 92 affected tests passed, including separate-process writes during a scan for single/sharded YAML, maintenance under changing signatures, bounded finalization, exact evidence projection and fail-closed source races. The adopted governance gate passed with 0 errors and 0 warnings; changed Python files passed Ruff. Protected OneDev and independent publication are the next delivery boundary. Native runtime is unchanged at this source checkpoint.
