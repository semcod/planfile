# Ticket 251: Use canonical dockuri Procache dependency

- **ID**: ticket-251
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-28

## Goal and scope

Replace the old subactor/procache requirement with dockuri/procache at the independently merged94cb311 revision. Update only its provenance in the existing lock; keep other dependencies stable. Preserve foreign ticket250.

SESSION_EXECUTION_AUTHORIZATION: user requested "kontynuuj, testuj, scalaj, wykonuj zalegle", continuing the authorized canonical-library migration and multi-provider cache work, including protected publication.

## Acceptance criteria

- [x] AC-01: Manifest and lock resolve canonical dockuri/procache94cb311 with no unrelated dependency changes.
- [ ] AC-02: Existing cache regressions, managed governance and protected Python3.10/3.11/3.13 verification pass using the candidate library.
- [ ] AC-03: Independent Validator approves the frozen exact head and the protected controller merges it.

## Delivery boundary

The protected OneDev dependency-input closure needs a separately owned exact revision before merge. Retain this ticket through publication; local checks alone do not grant approval.

Local evidence: all36 scoped provider-cache regressions pass with canonical Procache, the five installed module digests match94cb311, and managed governance passes. Parsed comparison of all123 locked packages proves that only Procache Git provenance changed. Full local verification is recorded externally; protected three-interpreter input qualification remains required before merge.
