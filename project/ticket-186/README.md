# Ticket 186: Atomic CLI dedupe-key with occurrence notes

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Owner**: agent:codex / codex-planfile186-oct4

SESSION_EXECUTION_AUTHORIZATION: the user requested continuation, tests and protected merges. Complete existing PLF-064. Own only the bounded ticket create/dedupe scope; concurrent ticket-185 owns sync watcher commands.

- [x] AC-01: CLI --dedupe-key atomically creates or appends the occurrence description/name to the existing live ticket; concurrent calls lose no notes.
- [x] AC-02: Reuse preserves original content, sprint and integration routing, synchronizing only the returned ticket. Terminal tickets release keys.
- [x] AC-03: No-sync/dry-run remain isolated; meaningful regressions, full suite, Ruff and managed governance pass.
- [ ] AC-04: Exact-head/base independent CI, Validator merge and installed CLI verification pass.

Validation: 8 regressions failed before implementation; 24 focused tests and 954 full tests passed, 6 skipped. Four independent CLI processes preserve all occurrences. Real GitHub canary reused and closed Issue #219. Ruff and managed governance passed. Exact-head/base OneDev and independent Validator merge remain required.
