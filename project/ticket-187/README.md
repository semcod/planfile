# Ticket 187: Verify GitHub redirects before preserving mappings

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Owner**: agent:codex / codex-planfile187-oct4

SESSION_EXECUTION_AUTHORIZATION: user requested continuation, tests and protected merges. Complete the remaining verified-redirect criterion of PLF-072 / GitHub #98. Existing atomic mapping and legacy migration implementation must be retained. The disjoint active ticket-185 owns sync watch commands.

- [x] AC-01: Existing mappings migrate only after fresh provider metadata verifies the same numeric repository identity and canonical destination.
- [x] AC-02: Local alias strings, unrelated/reused repository names, unavailable proof and conflicting binding cannot authorize remote mutations or destroy mappings.
- [x] AC-03: Dry-run is read-only; migrations preserve concurrent writes and exclude credentials; meaningful regressions, full tests, Ruff and governance pass.
- [ ] AC-04: Real read-only GitHub redirect canary, exact head/base OneDev, independent Validator merge and installed source readback pass.

GitHub reference: https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository and https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#follow-redirects . No repository rename or transfer will be performed for testing.

Validation: 13 regressions reproduced before implementation; 79 focused tests passed. Full suite against merged watch recovery: 985 passed, 6 skipped. Ruff and managed governance passed. Fresh real GitHub metadata verified twitter/bootstrap -> twbs/bootstrap (numeric ID 2126244), preserved mappings and rejected an unrelated repository without provider writes. Genuine SDK issue readback through the verified numeric repository route returned semcod/planfile#98. Exact-head/base OneDev and independent protected merge remain required.
