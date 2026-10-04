# Ticket184: Safe GitHub lifecycle status preflight

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Owner**: agent:codex / planfile184-status-20261004

SESSION_EXECUTION_AUTHORIZATION: user requested continuation, tests and protected merges. Resume PLF-105 / GitHub #214. Own only github.py, outbound.py and dedicated regression tests; foreign native183 owns retry/CLI files and must remain untouched.

- [x] AC-01: Legacy Ticket aliases map consistently to GitHub lifecycle.
- [x] AC-02: Invalid update status fails before body, labels, state or other provider writes.
- [x] AC-03: Regression, full suite and governance pass.
- [ ] AC-04: Exact-head independent CI/review/merge and installed source readback.

Validation: 11 old regressions failed before the fix; 40 focused tests pass; full suite 920 passed, 6 skipped. Ruff and managed governance pass. Protected preflight confirms configured authority; runtime/approval still require exact-head receipts.
