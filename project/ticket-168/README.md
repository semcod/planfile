# Ticket 168: expose next ticket batching and waves in cli

- **ID**: ticket-168
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-28

## Goal and scope

Expose batching options (`--count`, `--disjoint-files`) to `planfile ticket next` CLI command and add `planfile ticket waves` command to inspect topological execution waves directly from the CLI.

## Acceptance criteria

- [x] AC-01: `planfile ticket next` supports `-c` / `--count` and `--disjoint-files` / `--no-disjoint-files`.
- [x] AC-02: When count > 1, `planfile ticket next` outputs list of tickets in requested format (yaml/json).
- [x] AC-03: `planfile ticket waves` command returns topological layers / execution waves in table, json, or yaml format.
- [x] AC-04: Existing `planfile ticket next` behavior with default `count=1` remains backward-compatible.
- [x] AC-05: Unit tests cover `--count`, `--disjoint-files`, and `ticket waves`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
