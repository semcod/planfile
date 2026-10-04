# Ticket 190: Persist incremental GitHub selection and cooldown

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Owner**: agent:codex / codex-planfile190-oct4

SESSION_EXECUTION_AUTHORIZATION: user requested continued repairs, tests and protected merges. Complete PLF-091 / GitHub #196 using the existing fenced journal and native exact-ticket delivery.

- [x] AC-01: Persist new/changed revisions; skip current acknowledged unchanged records before provider initialization; preserve dirty state after failures and newer edits during delivery.
- [x] AC-02: Honor provider Retry-After across jobs in this repository and restarts, stop bounded cycles on rate limits, preserve exact ticket/sprint scope and read-only dry-run; reject unsupported directions/formats.
- [ ] AC-03: Meaningful regressions, full suite, Ruff, governance, same-issue real canary, exact head/base OneDev, independent protected merge and installed runtime pass.

Provider guidance: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#handle-rate-limit-errors-appropriately . Scope is this local repository, not an account-wide quota service. Legacy synchronization remains available separately.

Validation: 28 genuine before-fix regressions; final 137 focused tests; full suite 1064 passed / 6 skipped. Whole changed Python files pass Ruff and native governance. Existing closed GitHub #224 received A-to-B-to-A and the latest content after a controlled quota response and simulated clock window, survived restart and avoided backend initialization for unchanged content; no new issue was created. Current native exact-head/base OneDev, independent protected merge and installed CLI checks remain required.
