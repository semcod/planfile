# Ticket 277: update allocator highwater cache on ticket creation to prevent lock timeout on files > 5MB

- **ID**: ticket-277
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-11-03

## Goal and scope

Prevent locked rebuild timeouts and `allocator_evidence_changed_retry` errors on large sprint files (> 5MB) by atomically updating the allocator highwater cache on ticket persistence and increasing `MAX_LOCKED_REBUILD_BYTES` to 50MB.

## Acceptance criteria

- [x] AC-01: Ticket creation atomically maintains allocator highwater cache or supports large sprint files under lock
- [x] AC-02: Sequential ticket creation on sprints > 5MB succeeds without crashing with allocator_evidence_changed_retry
- [x] AC-03: Tests in tests/test_allocator_preparation.py and tests/test_allocator_dedupe.py pass

## Implementation details

- `planfile/core/allocator_sprints.py`:
  - Increased `MAX_LOCKED_REBUILD_BYTES` to 50,000,000 (50MB).
  - Factored out `save_sprint_highwater` helper.
  - Implemented `update_sprint_highwater_cache` to preserve existing prefix caches with the new file signature and update highwater marks for newly added tickets.
- `planfile/core/store.py`:
  - Called `update_sprint_highwater_cache` after atomic YAML write in `_create_ticket_unlocked` and `_create_tickets_bulk_unlocked`.
- `tests/test_allocator_preparation.py`:
  - Added `test_sequential_ticket_creation_on_large_sprint_succeeds_without_retry` verifying sequential ticket creations succeed with small `MAX_LOCKED_REBUILD_BYTES`.
