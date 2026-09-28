# Ticket 171: integrate planfile-graph rust acceleration into ticket graph and cycle validation

- **ID**: ticket-171
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-28

## Goal and scope

Integrate native Rust `planfile-graph` acceleration into `planfile.core.decompose` and `planfile.__init__`:
- Use `_native_validate_dag` for cycle detection in `add_dependency` and batch dependency operations.
- Use `_native_clean_ghost` in `prune_dangling_dependencies` for high-speed ghost blocker detection and removal.
- Ensure graceful fallback to Python Kahn/traversal algorithms when `planfile-graph` is absent.

## Acceptance criteria

- [x] AC-01: `add_dependency` validates against dependency cycles using native `validate_dag` with Python fallback.
- [x] AC-02: `prune_dangling_dependencies` utilizes `clean_ghost_dependencies` native acceleration when available.
- [x] AC-03: All tests in `tests/test_decompose.py` and `tests/test_native_acceleration.py` pass.
- [x] AC-04: `./project/governance-check.sh` passes with 0 errors and 0 warnings.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
