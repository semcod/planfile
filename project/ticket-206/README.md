# Ticket 206: Import current code2llm health reports as actionable quality tickets

- **ID**: ticket-206
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-08

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: The user requests continuation of the
Willman/Koru code quality pipeline based on project/analysis.toon.yaml.
Workspace PLF-013 / PLF-121 tracks this bounded parser repair. Current HEALTH
reports contain GOD, DUP and CYCLE alerts; the installed importer silently
returns no tickets because it only recognizes an older CC line format.
Parse current health alerts, preserve legacy CC/evolution support, restrict
parsing to HEALTH, and return ticket names accepted by Planfile persistence.
Retain report provenance, concrete module paths and stable dedupe labels.
Duplicate and cycle signals require triage; no executor or lease is inferred.

## Acceptance criteria

- [x] AC-01: Current GOD/DUP/CYCLE health alerts produce file-scoped or triage candidates instead of an empty result.
- [x] AC-02: Legacy CC and evolution imports retain their existing fields and behavior.
- [x] AC-03: Imported records persist with Planfile's normal bulk API; unrelated report sections cannot create tickets.
- [x] AC-04: Focused importer and persistence tests plus governance pass.

SESSION_EXECUTION_AUTHORIZATION (2026-10-08 continuation): The user says
"kontynuuj, scalaj, naprawiaj" after reviewing the tested local repair and
explicit publication question. This authorizes push, PR, independent protected
validation and gated merge of this bounded importer repair. Record actual merge
and activation externally; session prose never substitutes for trusted approval.

No dispatcher activation, Koru quality editing, protected policy changes or
version bump is part of this slice.
