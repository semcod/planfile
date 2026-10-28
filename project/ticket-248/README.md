# Ticket 248: Keep operational ticket intake and sync from blocking clean-primary execution

- **ID**: ticket-248
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user authorized autonomous execution, testing,
and merging of open blocking tasks (`kontynuuj, testuj, scalaj, wykonuj zalegle`),
including `semcod/planfile` Issue #304 (`PLF-20015`, deduplication key
`semcod/planfile:d2a989f6ada2f6b2:PLF-20015`).
maxActiveMinutes: 60.

This ticket provides a repository-bound operational intake store mode that routes
mutable operational ticket intake, allocator high-water state, and external sync
state/receipts to a Git-common-dir-backed operational store (`<git-common-dir>/planfile-operational/.planfile`
or configured `planfile.operationalStoreRoot`) outside tracked working-tree paths.
It preserves repository identity, GitHub sync bindings, `store_identity` deduplication
keys, CAS preconditions, cross-worktree visibility across primary and linked delivery
checkouts, interrupted-migration recovery, and non-destructive migration rollback.

## Acceptance criteria

- [x] AC-01: A disposable tracked-Planfile fixture can enable operational intake mode,
  create and sync a ticket through the normal SDK/CLI store contract, and keep
  `git status --porcelain --untracked-files=all` clean so clean-primary allocation succeeds.
- [x] AC-02: A real dirty tracked source file in the primary checkout still marks the
  working tree dirty and refuses clean-primary admission.
- [x] AC-03: Non-destructive operational store bootstrap, interrupted-migration recovery,
  and rollback preserve allocator high-water IDs, ticket records, `store_identity`,
  and GitHub sync mappings without resetting or deleting tracked checkout files.
- [x] AC-04: Round-tripping the same ticket across the primary checkout, a linked
  delivery worktree, and the FastAPI server reads and mutates the shared operational
  store with consistent CAS and sync state.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
