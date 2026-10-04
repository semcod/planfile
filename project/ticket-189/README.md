# Ticket 189: Retain provider cooldown across completion edits

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Owner**: agent:codex / codex-planfile189-oct4

SESSION_EXECUTION_AUTHORIZATION: user requested continuation, repairs, tests and protected merges. Finish the remaining cooldown criterion of PLF-089 / GitHub #194 after PR #225 landed its initial implementation. Preserve the tested uncommitted refinement from the now-integrated ticket-188 in a new active native scope.

- [x] AC-01: New completion content retains attempts, sanitized failure history and the provider retry deadline across repeated queued edits.
- [x] AC-02: YAML/sharded regressions, existing revision fencing tests, full suite, narrow/default/wide terminal schema assertions, Ruff and native governance pass; real delivery updates the same issue only after cooldown.
- [ ] AC-03: Exact-head/base OneDev and independent protected merge, installed runtime readback and scoped closure of the source task.

No global provider pause, incremental selection, new dependency, fleet deployment or default network effects.

Full-suite observation exposed a pre-existing assertion that assumed a long path could never wrap. The bounded test-only repair normalizes line breaks for the path assertion and checks terminal widths 40, 80 and 120. Schema validation and runtime behavior remain covered by their original assertions.

Validation: 132 focused synchronization/API tests, 6 schema tests, full suite 1021 passed / 6 skipped. Both cooldown regression variants genuinely failed before the fix. The initial full-suite run found the path-wrapping assertion; the repaired full suite passed at the original long temporary path. Whole-file Ruff and native governance passed. The real same-issue canary updated closed GitHub #224 with the latest payload after the preserved cooldown and created no issue. Independent exact-head/base publication and installed runtime readback remain required.
