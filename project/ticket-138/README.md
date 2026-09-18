# Ticket 138: Pin procache with Python 3.10 compatibility

- **ID**: ticket-138
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

## Goal and scope

Keep the shared Python dependency manifest and lockfile compatible with every
Python version supported by Planfile.

## Acceptance criteria

- [ ] AC-01: Locked dependency installation resolves on Python 3.10 and 3.13.
- [ ] AC-02: The procache pin references the tested Python 3.10 compatible commit.

## Tracking boundary

This ticket owns only dependency manifest and lockfile integration.
