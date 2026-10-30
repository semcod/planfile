# Ticket 260: Close SQLite index connections and preserve busy rebuild owners

- **ID**: ticket-260
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-30

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue the user's autonomous repair, testing and independent publication work. Existing owner semcod/planfile#313, parent PLF-20347 / Willman430. Prior isolated diagnostics proved100status reads retained201additional descriptors while cyclic GC was disabled, and a forced rebuild replaced the index inode while an independent SQLite writer was alive. Fix the component lifetime and contention classification, preserving real corruption recovery and durable authoritative state. Current internal health/summary reads work while archived operational reads exceed deadlines; source changes alone do not prove native service recovery.

## Acceptance criteria

- [x] AC-01: Internal index operations close connections deterministically, including transaction and setup failures, without requiring cyclic GC.
- [x] AC-02: BUSY/LOCKED rebuilds preserve the active database and owner; independent-process and corruption-recovery regressions pass.
- [ ] AC-03: Affected checks, protected exact-head CI and independent publication pass; an installed immutable candidate has separate canary evidence and no implicit live rollout.

## Delivery boundary

Never remove a live lock/index, kill a writer, forge a historical publication receipt, hotpatch the live package or equate source tests with deployment. Preserve existing313/316/317 and Validator593 evidence. Allocation uses the installed ID-only allocator; delivery uses the adopted v5 planner and canonical relative worktree.

Independent Validator review correction: the repeated-read regression now retains all 200 real SQLite connections and proves each is closed on every platform. Linux additionally measures `/proc/self/fd`; no regression is skipped. The same 78 affected tests pass with the updated test, and pinned Ruff 0.15.11 reports no findings. Source behavior and the installed artifact bytes are unchanged; fresh exact-head CI and independent approval remain required.
