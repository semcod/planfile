# Ticket 201: Reconcile silent broad exceptions in file analyzer and DSL executor

- **ID**: ticket-201
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-06

## Goal and scope

Reconcile Doctor code-search findings (#421 and #422 / PLF-16993, PLF-16994) regarding `python.silent-broad-except` in `planfile/analysis/file_analyzer.py` and `planfile/dsl/executor.py`. Ensure exceptions are logged with appropriate error/debug signals rather than silently suppressed, while preserving fallback behavior and propagation of control-flow exceptions like `TimeoutError`.

## Acceptance criteria

- [x] AC-01: In `planfile/analysis/file_analyzer.py`, native analyzer failure logs a debug error signal before falling back to text analysis, while `TimeoutError` remains raised.
- [x] AC-02: In `planfile/dsl/executor.py`, `_nl_to_dsl_fallback` and conversational queries log debug error signals on exception instead of silent discarding.
- [x] AC-03: Add comprehensive regression tests in `tests/test_file_analyzer_error_signal.py` and `tests/test_dsl_executor_error_signal.py`.
- [x] AC-04: Existing test suite passes and `./project/governance-check.sh` reports `GOV-PASS`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
