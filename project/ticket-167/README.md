# Ticket 167: Preserve LLM context and timeout inputs

- **ID**: ticket-167
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

SESSION_EXECUTION_AUTHORIZATION: user requests live evaluation of small Koru issues and authorizes repairing Koru dependencies and protected merge (2026-09-28).

## Goal and scope

Real execution of Koru issue #385 dropped inputs.context_files and llm_timeout_seconds during native Planfile creation. Koru therefore received no source context and completed an incorrect answer. Preserve the five existing context/timeout inputs consumed by Koru; do not claim this supplies semantic answer verification.

## Acceptance criteria

- [x] AC-01: Typed inputs preserve explicit context selectors, budget and timeout across create/update/read/CLI; omitted inputs retain legacy serialization.
- [ ] AC-02: Regression and governance checks pass; protected exact-head publication completes.

Bounded session: maxActiveMinutes=120, checkpointMinutes=30.

## Validation

55 focused contract, storage, CLI, API, execution and partial-update tests passed. The regression failed before the change because all five supplied fields disappeared. Managed governance passed; protected review/merge remains pending.
