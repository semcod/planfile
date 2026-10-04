# Ticket 182: Bound Planfile store lock waits

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Workstream**: application

SESSION_EXECUTION_AUTHORIZATION: wykonaj; parent Planfile PLF-102 / GitHub #208.

## Acceptance criteria

- AC-01: Contending mutation/index locks raise a clear bounded timeout.
- AC-02: A timeout does not unlock or replace the holder lock, edit ticket files, or kill processes.
- AC-03: After holder exit/crash another writer can proceed without data loss.
- AC-04: Nested acquisition reports timeout instead of waiting forever.

Validation: multiprocessing contention/crash tests and store/index regression suites.

Validation: 67 tests passed (176.51 s); Ruff and managed governance passed. Live search lock timeout: 0.213 s, owner PID 3102639 retained.
