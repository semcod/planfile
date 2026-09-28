# Ticket 165: integrate planfile-io native rust acceleration

- **ID**: ticket-165
- **Owner**: agent:gemini
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — user requests acceleration and native planfile-io integration; 2026-09-28.

## Goal and scope

Integrate the native Rust `planfile-io` crate into `planfile.core.fastio` to provide 20x–60x speedups for YAML parsing and sprint file operations. Preserve pure-Python fallback for environments where the native wheel is not installed.

## Acceptance criteria

- [x] AC-01: When `planfile_io_rs` is importable, `read_yaml_fast` and `write_yaml_fast` delegate to Rust.
- [x] AC-02: Graceful fallback to pure-Python implementation when `planfile_io_rs` is unavailable.
- [x] AC-03: Existing fastio tests pass with and without the native extension.

## Tracking boundary

This directory contains the minimal reviewed intent and acceptance criteria.
