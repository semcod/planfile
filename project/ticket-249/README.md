# Ticket 249: Return typed retryable API refusal on real ticket-store lock contention

- **ID**: ticket-249
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user authorized autonomous execution, testing,
and merging of open blocking tasks (`kontynuuj, testuj, scalaj, wykonuj zalegle`),
including `semcod/planfile` Issue #299 (`PLF-19993`, deduplication key
`semcod/planfile:d2a989f6ada2f6b2:PLF-19993`).
maxActiveMinutes: 47.

Translate proven pre-commit `StoreLockTimeoutError` contention in the FastAPI server
into a documented, typed retryable HTTP 503 response (`detail: "ticket_store_lock_timeout"`,
`code: "ticket_store_lock_timeout"`, `retryable: true`, `Retry-After: 5`) without
exposing host filesystem paths, PIDs, or credentials. Preserve writer ownership,
lock lifetime, ticket state, `execution.attempt`, CAS preconditions, and evidence
idempotency across all mutation endpoints without silently replaying non-idempotent
mutations.

## Acceptance criteria

- [x] AC-01: Under real separate-process `fcntl.flock` store-lock contention, API
  mutation endpoints (`PATCH /tickets/{id}`, `POST /tickets/{id}/update-if-current`,
  `POST /tickets`, `POST /tickets/{id}/claim`, `POST /tickets/{id}/start`,
  `POST /tickets/{id}/complete`, `POST /tickets/{id}/fail`,
  `POST /tickets/{id}/evidence`, `POST /dsl`, `PATCH /yaml`) return bounded HTTP 503
  with `Retry-After: 5` and typed JSON (`detail: "ticket_store_lock_timeout"`,
  `retryable: true`) without leaking host paths or PIDs.
- [x] AC-02: Contention refusal preserves the active writer's lock file inode and
  process, leaves sprint YAML, ticket state, `updated_at`, `execution.attempt`, and
  evidence journals untouched, and does not silently replay non-idempotent mutations.
- [x] AC-03: After the separate-process lock holder releases the lock, subsequent
  mutations, CAS checks (`409`), terminal reopen guards (`409`), and idempotent/conflicting
  evidence appends (`200`/`409`) succeed normally while unexpected errors still
  surface as HTTP 500.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
