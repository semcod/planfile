# Ticket 210: Cache allocator journal high-water

- **ID**: ticket-210
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue requested autonomy repairs and protected publication. Implements semcod/planfile PLF-17309. Avoid decoding the full operations journal on every allocation using a derived, file-identity-bound cache maintained by the existing locked append path. Preserve ticket and sync evidence scans. Cold/replaced/modified journals rebuild via streaming; preserve journal contents and reservation correctness.

## Acceptance criteria

- [x] AC-01: Repeated allocations reuse the journal high-water across store instances and locked appends.
- [x] AC-02: External changes, truncation, replacement and invalid caches trigger reconstruction; deleted IDs remain reserved.
- [x] AC-03: Cold scan uses bounded memory; concurrency and ID regressions pass.
- [ ] AC-04: Governance, protected review/merge and deployed measurement have separate receipts.

## Validation

17 focused tests and governance passed. Synthetic 42 MB journal: cold 0.124 s, warm 0.00013 s; excludes ticket and sync scans. Protected CI and deployed readback remain AC-04.
