# Ticket 208: Sort inbound sync imports to restore Planfile CI after CAS repair

- **ID**: ticket-208
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-10-11

## Goal and scope

Sort inbound sync imports in `planfile/sync/operations.py` to restore Planfile CI after CAS repair (#254 / PLF-13805).

## Acceptance criteria

- [x] AC-01: Imports sorted according to ruff I001 (`import re` before `from copy import deepcopy`).
- [x] AC-02: All 22 tests in `tests/test_sync_inbound_sdk_revision.py` pass cleanly.
- [x] AC-03: Zero-warning governance check passes.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
