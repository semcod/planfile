# Ticket 203: Reconcile silent broad exceptions in task decomposition graph fallbacks

- **ID**: ticket-203
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Reconcile Doctor code-search findings (#417 / PLF-16681) regarding `python.silent-broad-except` in `planfile/core/decompose.py` (lines 191, 226, 267, 445, 481). Ensure native Rust graph fallbacks log appropriate debug error signals rather than silently suppressing exceptions, while preserving Python fallback computation and graph validity.

## Acceptance criteria

- [x] AC-01: In `planfile/core/decompose.py`, log debug error signals when native Rust graph calls fail (`_native_validate_dag`, `_native_clean_ghost`, `_native_execution_layers`) before falling back to Python implementations.
- [x] AC-02: In `planfile/core/decompose.py`, log debug error signal when weight calculation fails in `critical_path`.
- [x] AC-03: Add comprehensive regression tests in `tests/test_decompose_error_signal.py`.
- [x] AC-04: Existing test suite passes and `./project/governance-check.sh` reports `GOV-PASS`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
