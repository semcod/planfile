# Ticket 197: Safe legacy sprint YAML migration

- **ID**: ticket-197
- **Owner**: gemini
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Authorized by the user ecosystem implementation request and continuation (Issue #195).
Detect legacy top-level `tasks` lists before interpreting `planfile.sprint/v1`.
Provide safe explicit migration preserving ticket IDs, titles/names, and metadata.
Emit useful schema errors instead of unhandled `AttributeError` on non-dict ticket mappings or malformed sprint shapes.
Ensure idempotent repeated migration and guard against silent destructive rewrites.

## Acceptance criteria

- [x] AC-01: Detect legacy top-level `tasks` lists during schema validation and document type detection, reporting clear diagnostic errors.
- [x] AC-02: Guard sprint ticket loading and iteration against non-dict `tickets` structures, preventing unhandled `AttributeError`.
- [x] AC-03: Provide explicit safe migration from legacy `tasks` lists to `sprint.tickets`, preserving IDs, titles/names, and all custom metadata.
- [x] AC-04: Ensure repeated migration is idempotent and does not overwrite or drop existing valid tickets.
- [x] AC-05: Add comprehensive regression tests and ensure all tests pass and governance checks exit 0.

## Tracking boundary

Parent task: Issue #195. This ticket delivers bounded sprint schema validation, legacy task migration, and error handling without mutating foreign formats.
