# Ticket 074: Relock uv.lock after pfix removal

- **ID**: ticket-074
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: on 2026-09-13 the user asked to remove or
deactivate pfix in the projects; on 2026-09-14 to find and fix what blocks
code delivery. This ticket repairs a regression of that removal.

`de3e6a6` (semcod/planfile#77) removed the pfix dev requirement from
`pyproject.toml` but left `uv.lock` unchanged, so `uv lock --check` fails on
`main` and `uv sync --locked` refuses to install. Before that commit the lock
was consistent. Relock with the pinned `uv 0.12.13`; the lock diff only drops
pfix entries.

The manifest assigned `uv.lock` to no workstream, which is why the earlier
ticket could not include it. This ticket adds `uv.lock` to the `integration`
workstream next to `pyproject.toml`.

Non-goals: no dependency upgrade, no source or test change, no release.

## Acceptance criteria

- [ ] AC-01: `uv lock --check` passes on the exact head and the lock diff only
  removes pfix entries.
- [ ] AC-02: The governance gate passes on the exact head.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
