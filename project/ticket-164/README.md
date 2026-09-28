# Ticket 164: Preserve ticket file-change execution contract

- **ID**: ticket-164
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — user requests Koru repair, pilot execution and meaningful verification; continued 2026-09-28.

## Goal and scope

The isolated c2004 PLF-2657 pilot discovered that Planfile drops
`inputs.expect_files_changed` while creating a ticket. Koru then accepts an
exit-zero shell command without the requested output. Preserve explicit
boolean expectations through the native model, store and CLI. Keep an omitted
expectation absent so existing Koru refactor/code-change inference still works.
Source tracking: Planfile PLF-087; failed pilot receipt stays in ignored recovery.

## Acceptance criteria

- [x] AC-01: Explicit true/false survive native create/update/read and CLI JSON.
- [x] AC-02: Omitted values stay omitted; nonboolean contract values fail validation.
- [x] AC-03: Partial updates keep the existing expectation and targeted tests pass.
- [ ] AC-04: Governance passes; publication requires exact-head independent Validator.

## Tracking boundary

This ticket owns the bounded model/test change. Raw operational receipts stay
in ignored recovery; c2004 PLF-2657 retains the incomplete runtime acceptance.
