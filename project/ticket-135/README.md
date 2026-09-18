# Ticket 135: Bound project-root discovery outside Git repositories

- **ID**: ticket-135
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

## Goal and scope

Prevent `canonical_project_root` from adopting an unrelated ancestor
`.planfile` when the calling path is outside any Git repository. Explicit paths
inside an existing `.planfile` remain supported.

## Acceptance criteria

- [ ] Discovery from a non-Git nested path does not cross into an ancestor store.
- [ ] Discovery from an explicit store path still resolves its project root.
- [ ] Existing Git-bounded discovery behavior remains unchanged.
- [ ] Focused tests and managed governance pass.

## Tracking boundary

This directory contains the reviewed intent and delivery evidence.
