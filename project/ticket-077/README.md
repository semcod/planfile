# Ticket 077: Resolve the accepted base in locked tests

- **ID**: ticket-077
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-14

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested implementation, testing, repairs and protected publication of the Koru/Planfile workflow. Hosted tests for ticket-076 fail before test collection because a shallow checkout omits the accepted base SHA. Fetch full history without bypassing the gate.

## Acceptance criteria

- [x] AC-01: Locked Python matrix jobs use full Git history and retain all existing test and governance checks.
