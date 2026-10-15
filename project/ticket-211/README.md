# Ticket 211: Cache allocator sprint identity evidence

- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Planfile**: PLF-18397

## Authorization

SESSION_EXECUTION_AUTHORIZATION: user requested continued repairs and protected merges.

## Scope

Cache per-sprint numeric identity evidence without retaining full archive data in memory. Preserve ID, label and description reservations. Rebuild on source identity change or damaged cache; retain original sharded behavior. No public API or dependencies change.

## Acceptance criteria

- AC-01: Repeated allocation avoids decoding unchanged archive contents.
- AC-02: External replacement, edits, deletions and damaged caches trigger source reconstruction.
- AC-03: Existing ID reservation semantics remain intact.
- AC-04: Protected publication checks and independent merge receipt.
