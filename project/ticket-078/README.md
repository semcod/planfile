# Ticket 078: Fail closed on partial external ticket synchronization

- **ID**: ticket-078
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested continued repair, tests,
push and protected merge, and explicitly authorized --force-new on 2026-09-15
for a separate ticket addressing semcod/planfile#88. Do not change ticket-073
or the dirty primary checkout. The allocator reserved this ID clone-wide
before this separate canonical worktree was created.

Bounded slice: outbound sync must preserve successful mappings, report partial
failure to callers and exit nonzero instead of printing overall success.
Keep later tickets attempted and make retry update already synchronized tickets.
No live fault injection, deployment, credentials, policy changes, inbound-sync
redesign or repository-scoped outbox migration. Remaining #88 criteria stay open.

Ownership adjustment: the commit guard found an independent dirty radar
projection in operations.py in the ticket-radar checkout. Preserve that file
byte-for-byte; the CLI uses a new outbound batch module that reuses its existing
create/update/persistence helpers. Direct users of the old
operations.sync_to_external function retain legacy behavior until a coordinated
follow-up. No competing writer, ignore rule or hook is changed.

## Acceptance criteria

- [x] AC-01: Separate allocation and implementation scope are authorized.
- [x] AC-02: Outbound create/update failures yield a typed aggregate failure
  after successful mappings are saved, with deterministic per-ticket outcomes.
- [x] AC-03: CLI exits nonzero without a success banner on partial failure;
  dry-run and complete success remain compatible. Bidirectional sync does not
  import over local work after outbound failure.
- [x] AC-04: Offline regressions cover partial batches, mapping persistence,
  retry, update/replacement failure and CLI exit behavior; governance passes.
- [ ] AC-05: Publish only through independent exact-head Validator and required
  repository checks; no release or installed-runtime update is claimed.

## Validation

- Before implementation: 10 new regression failures, including exit 0 after a
  controlled offline backend failure; 3 compatibility checks passed.
- After implementation: 19 focused tests passed.
- Full locked Python 3.13 suite: 538 passed, 6 existing skips, 11 warnings in
  60.02 seconds after the ownership adjustment. No skip or test configuration
  was added by this ticket. The 19 focused tests passed again.
- Managed governance: PASS, 0 errors and warnings. Scoped Ruff and whitespace:
  PASS. Compose configuration: PASS with existing missing-environment and
  obsolete-version warnings; no services were started.
- Worktree overlap guard: PASS, 23 checkouts inspected. Wheel and sdist build:
  PASS, the wheel contains sync/outbound.py.
- Protected profile retains ci-loop and notify. No OneDev profile for Planfile
  was present in the observed deployment; exact-head hosted checks and the
  independent local Validator still gate publication.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
