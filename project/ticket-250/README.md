# Ticket 250: Prevent fastio reads from rewriting tracked mirrors and add PLANFILE_MIRROR_WRITE

- **ID**: ticket-250
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-28

## Authorization
SESSION_EXECUTION_AUTHORIZATION: User authorized autonomous execution to resolve semcod/planfile#272.

## Goal and scope

Prevent `planfile.core.fastio` reads and mirror writes from rewriting Git-tracked `*.fast.json` mirror files (which previously dirtied fresh checkouts and worktrees when mtime differed), report tracked mirrors in `audit_mirror`, and add the `PLANFILE_MIRROR_WRITE=0` environment switch for side-effect-free read-only consumers.

## Acceptance criteria

- [x] AC-01: `find_tracked_mirrors` and `is_tracked_mirror` identify Git-tracked `*.fast.json` files and prevent `write_mirror`, `write_sprint_native`, and `read_yaml_fast` from rewriting them, keeping `git status --porcelain` empty on reads in fresh worktrees.
- [x] AC-02: `PLANFILE_MIRROR_WRITE=0` (`false`/`no`/`off`) disables `.fast.json` mirror writes for read-only consumers.
- [x] AC-03: `audit_mirror` flags tracked mirrors (`ok=False`, `healed=False`) without dirtying the working tree.
