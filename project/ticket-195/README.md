# Ticket 195: Skip non-whitelisted hidden directories and prioritize per-file size bounding in FileAnalyzer

- **ID**: ticket-195
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

1. In `FileAnalyzer.analyze_directory`, prune all hidden directories except `.github` during directory traversal (`d.startswith('.') and d != '.github'`), preventing traversal into ad-hoc and tooling hidden directories (`.intent-*`, `.benchmarks`, `.koru`, `.nlp2dsl`, `.taskill`, `.tillm`, `.pyqual`, `.redsl`, etc.).
2. In `FileAnalyzer.is_excluded`, treat any directory component starting with `.` other than `.github` as excluded.
3. In `FileAnalyzer.analyze_directory`, evaluate `max_single_file_bytes` before checking `max_bytes` total truncation, so an oversized file (> 1 MB) is recorded as a structured diagnostic issue and skipped, rather than prematurely exhausting `max_bytes` (25 MB) and causing repository scans to be falsely marked as `truncated: true` / `HEALTH_BUDGET_EXCEEDED`.
4. Ensure `planfile health check .` runs with `status: ok` and `truncated: false`.

## Acceptance criteria

- [x] AC-01: `FileAnalyzer` prunes non-whitelisted dot-directories during traversal and treats them as excluded while preserving `.github`.
- [x] AC-02: `FileAnalyzer.analyze_directory` checks `max_single_file_bytes` before `max_bytes`, so oversized files do not trigger repository-level budget truncation.
- [x] AC-03: `planfile health check .` on the repository produces `status: ok` and `truncated: false`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
