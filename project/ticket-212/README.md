# Ticket 212: Bound cold allocator evidence reconstruction

- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Planfile**: PLF-18410

## Authorization

SESSION_EXECUTION_AUTHORIZATION: continue repairs, optimization and protected merges.

## Scope

Warm large sprint allocator evidence outside the mutation lock for all ID allocating entry points. Revalidate exact file identity under lock; fail closed on a large cache miss instead of parsing an archive under the lock. Keep only bounded scalar evidence in memory when disk cache publication fails. Unrelated mutations do not trigger warmup. Remaining full API dedupe profiling is followup, not part of this slice.

## Acceptance criteria

- AC-01: Large cold reconstruction precedes acquisition of the mutation lock.
- AC-02: Changed or newly added large source cannot use stale identity evidence.
- AC-03: next_id, normal/deduplicated create, bulk, DSL and delivery-plan allocations use preparation.
- AC-04: Protected CI and independent Validator approve exact head before merge.
