# Ticket 194: Bound health check operational directory exclusion and single file size

- **ID**: ticket-194
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Bound `FileAnalyzer` and `planfile health check` by:
1. Excluding operational and non-source directories (`.subactor`, `.worktrees`, `.planfile`, `.governance`, `.intent`, `analyses`) and pruning them during directory traversal to avoid scanning thousands of transient agent artifacts.
2. Imposing a per-file size limit (`max_single_file_bytes = 1_048_576`) before invoking `yaml.safe_load` / text parsers, preventing individual multi-megabyte fixtures from consuming unbounded CPU and memory.
3. Enabling periodic inbound polling in `planfile sync watch` when `direction == "both"` while local `.planfile` files are idle, resolving remote issue status without redundant outbound writes.

## Acceptance criteria

- [x] AC-01: `FileAnalyzer` excludes operational directories (`.subactor`, `.worktrees`, `.planfile`, `.governance`, `.intent`, `analyses`) and prunes directory traversal before recursing.
- [x] AC-02: `FileAnalyzer.analyze_directory` skips files exceeding `max_single_file_bytes` and reports a structured diagnostic rather than attempting unbounded PyYAML parses.
- [x] AC-03: `planfile health check` runs in < 2 seconds on the local repository rather than exceeding the 8.0s timeout.
- [x] AC-04: `planfile sync watch` in `both` mode periodically triggers inbound synchronization when local files are unchanged.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
