# Ticket 336 · Recover journal-only index drift

- **ID**: ticket-336
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-25

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION covers implementation, regression testing and protected publication for the continuing Planfile queue repair. An interrupted evidence append can leave a committed journal entry and an older SQLite generation. On restart, the maintenance worker must be able to repair that bounded delta. Tracked under semcod/planfile:PLF-29323 and semcod/planfile#403.

## Acceptance criteria

- [x] AC-01. Reproduce first and subsequent interrupted receipt appends through the public API and repair from a fresh process-local store without scanning unrelated sprints.
- [x] AC-02. Check journal evidence in the current SQLite projection and preserve existing source, locator and budget checks.
- [ ] AC-03. Submit the tested change to the registered CI and independent Validator.
