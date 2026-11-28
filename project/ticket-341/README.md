# Ticket 341: Warn when inbound GitHub sync keeps a conflicting local status (#489)

- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-28
- **SESSION_EXECUTION_AUTHORIZATION**: the repository owner asked in the session to
  investigate GitHub issue synchronization and fix what does not work.

## Goal and scope

`sync github --direction from` reports success while keeping an immutable local
status that disagrees with the issue state. Print the conflict; change no statuses.

## Acceptance criteria

- [ ] AC-01: inbound sync warns when the preserved local status disagrees with the issue state.
- [ ] AC-02: neither side's status changes and matching states stay quiet.
