# Ticket 200: NL URI ticket commands and shared compiler adapter

- **ID**: ticket-200
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Implement exact natural language URI ticket commands parsing, shared compiler adapter for `wellmanifest.nl-plan/v1`, exact URI validation, ambiguity abstention, and dry-run preflight effects in Planfile DSL engine (`planfile/dsl/parser.py`, `planfile/dsl/executor.py`, `tests/test_dsl_uri_commands.py`). Resolves Issue #203 / PLF-099.

## Acceptance criteria

- [x] AC-01: Parse and validate `planfile://` and `uri: planfile://` command URIs (`tickets/command/create`, `tickets/{id}/command/{action}`, `tickets`, `sprints/{sprint}/tickets`, `sync`, `config`).
- [x] AC-02: Enforce exact URI validation and reject malformed/unsupported URIs with explicit ambiguity abstention.
- [x] AC-03: Provide adapter for `wellmanifest.nl-plan/v1` supporting `call`, `sequence` (1-16 calls), `clarify`, and `unsupported` envelopes.
- [x] AC-04: Authoritative allocator integration on creation and dry-run preflight support across mutating operations without persistent side-effects.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
