# Ticket 252: Untrack generated fastio sidecar mirrors from Git

- **ID**: ticket-252
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-28

## Goal and scope

Assign `.planfile/**/*.fast.json` to `governance.ownedPaths` in `.governance/manifest.json` and untrack the generated `.planfile/*.fast.json` sidecar mirrors from Git index so read-only CLI/pytest operations cannot dirty tracked files (closes #272).

- `SESSION_EXECUTION_AUTHORIZATION`: autonomous session execution requested by user.

## Acceptance criteria

- [x] AC-01: Add `.planfile/**/*.fast.json` to `governance.ownedPaths` in `.governance/manifest.json` and update `.governance/standard-adoption.json`.
- [x] AC-02: Remove `.planfile/config.yaml.fast.json`, `.planfile/sprints/backlog.yaml.fast.json`, and `.planfile/sprints/current.yaml.fast.json` from the Git index while keeping `*.fast.json` ignored in `.gitignore`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
