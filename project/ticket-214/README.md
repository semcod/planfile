# Ticket 214: Publish a machine-readable ticket status contract

- **ID**: ticket-214
- **Owner**: claude
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-15

## Goal and scope

Queue consumers outside planfile keep private copies of the status
vocabulary. On 2026-10-15 `monag resume` did not know `failed`, counted it as
an unknown status, and the fleet admission gate then refused willman project
intake for every repository holding one failed ticket (352 local
repositories; fixed in semcod/monag#141).

planfile now publishes `planfile/schemas/ticket-status.v1.json`
(`planfile.ticket-status/v1`): every `TicketStatus` value with a class and a
`pending` flag. `blocked` and `failed` are `stalled` (pending, never ready),
matching their existing behaviour (`failed` = execution attempts exhausted,
reopenable). `schemas/*.json` is already package data, so the contract ships
with every installation. A test fails if the enum and the contract diverge.

## Acceptance criteria

- [x] AC-01: `tests/test_ticket_status_contract.py`: the contract lists exactly
  the `TicketStatus` values, each with a declared class and a consistent
  `pending` flag; only `open` is ready; `blocked`/`failed` are stalled.
- [x] AC-02: full test suite: 1244 passed, 6 skipped.
- [x] AC-03: `project/governance-check.sh` passes.

## Tracking boundary

Adoption by consumers (monag) is a separate ticket in their repositories.
