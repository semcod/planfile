# Ticket 147: Preserve Planfile ticket IDs across journal history

- **ID**: ticket-147
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT

## Scope

Prevent the allocator from reusing a ticket ID that only exists in the
append-only event journal after the ticket was deleted or archived.

## Acceptance criteria

- [ ] A configured `next_id` below a journaled ticket ID is advanced before allocation.
- [ ] The allocator keeps existing active and archived IDs reserved.
- [ ] A regression test covers a deleted ticket that remains in the journal.
