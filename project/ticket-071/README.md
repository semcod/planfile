# Ticket 071: Bind MCP DSL to the exact allowed project

- **ID**: ticket-071
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **GitHub Issue**: https://github.com/semcod/planfile/issues/74
- **Planfile intake**: semcod/planfile::PLF-002

## Cel i Zakres
Prevent MCP DSL from reading or writing an ancestor project outside the explicit allowed root. Session execution and protected publication authorized by the user's continuation.

## Kryteria Odbioru
- [ ] AC-01: Parent/child and symlink fixtures cannot escape the selected project's storage boundary.
- [ ] AC-02: Initialized projects remain isolated; uninitialized explicit roots fail clearly; CLI discovery behavior stays compatible.

## Ryzyka i Uwagi
The primary checkout predates governance and contains unrelated changes. The unmodified allocator from published main was executed against an isolated source export, with the actual clone Git directory and high-water lock. It allocated ticket-071 before worktree creation. Source edits occur only in the canonical linked worktree. Read-only inventory found no competing dirty or branch contribution in the two scoped files.
This record grants no trusted merge approval. Existing stores and worktrees are preserved.
