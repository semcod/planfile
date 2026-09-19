# ticket-152 — Surface quota before SDK retry

- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Owner**: codex:monag-triage-cache-20260919

SESSION_EXECUTION_AUTHORIZATION: execute confirmed synchronization defect PLF-077. Package adoption is isolated in integration ticket-151 / PLF-078.

- [x] AC-01: Disable PyGithub transport retry so durable outbound handling receives quota errors immediately.
- [x] AC-02: Constructor regression preserves Retry-After and exception identity; full suite/governance pass.

Validation: 671 tests passed, 6 optional integration skips; 16 focused quota/transport regressions pass. The corrected native sync successfully created the queued project Issues without SDK backoff.
