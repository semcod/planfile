# Ticket 072: Remove pfix auto-repair from packaging metadata

- **ID**: ticket-072
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: on 2026-09-13 the user stated that pfix, the
development-time auto-repair tool, overwrites changes and must be removed from
Semcod projects or deactivated, and on 2026-09-14 authorized publication
through pull requests and the independent Validator.

This project declares `[tool.pfix]` with `auto_apply = true`,
`auto_install_deps = true` and `create_backups = false`, plus a pfix dev
requirement. This integration ticket removes those declarations. It replaces
closed PR #76, whose ticket was scaffolded without the managed allocator.

Non-goals: no source or test change, no release, and no `uv.lock` change
because `.governance/manifest.json` assigns `uv.lock` to no workstream.

## Acceptance criteria

- [ ] AC-01: `pyproject.toml` declares no `[tool.pfix]` table or pfix
  requirement; every other parsed value is unchanged; the governance gate passes.

Fleet evidence: `subactor/docs/architecture/analysis/semcod-library-quality.md`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
