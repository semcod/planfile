# Ticket 200 - NL URI ticket commands and shared compiler adapter

## Objective
Implement exact natural language URI ticket commands parsing, shared compiler adapter for `wellmanifest.nl-plan/v1`, exact URI validation, ambiguity abstention, and dry-run preflight effects in Planfile DSL engine (`planfile/dsl/parser.py`, `planfile/dsl/executor.py`, `tests/test_dsl_uri_commands.py`). Resolves Issue #203 / PLF-099.

## Requirements
- Support `planfile://` and `uri: planfile://` command URIs:
  - `planfile://tickets/command/create`
  - `planfile://tickets/{id}/command/{action}`
  - `planfile://tickets/{id}`
  - `planfile://tickets`
  - `planfile://sprints/{sprint}/tickets`
  - `planfile://sprints/command/create`
  - `planfile://sprints/{sprint}`
  - `planfile://sprints`
  - `planfile://sync`
  - `planfile://config`
  - `planfile://config/{path}`
  - `planfile://config/command/set`
  - `planfile://validate`
- Exact URI validation & Ambiguity abstention:
  - Reject malformed schemes, empty paths, unmapped actions, and query strings/fragments per `SEMANTIC_NL_PLAN.md`.
  - Malformed JSON arguments rejected with explicit error message; executor abstains from execution.
- Authoritative store allocator:
  - Ticket ID creation remains authoritative through Planfile store allocator.
- Dry-run preflight:
  - Support `dry_run=True` across mutating verbs (`create`, `update`, `done`, `start`, `block`, `delete`, `move`) without side-effects on disk.
- Envelope adapter for `wellmanifest.nl-plan/v1`:
  - Handle `ok` with `call` or `sequence` (1-16 calls).
  - Handle `clarify` and `unsupported` envelopes without execution.
