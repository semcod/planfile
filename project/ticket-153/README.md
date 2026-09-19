# Ticket153: Native GitHub lifecycle import

- **ID**: ticket-153
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Workstream**: application
- **Owner**: agent:codex-monag-triage-cache-audit

SESSION_EXECUTION_AUTHORIZATION: user requested fixes for verified MONAG/Planfile audit defects, including publication. Native ticket PLF-079 / GitHub Issue161.

## Acceptance criteria

- [ ] AC-01: GitHub closed/open updates and imports remain readable by the native store; preserve richer local lifecycle and distinguish not_planned from completed. Unknown close reasons do not claim completion.
- [ ] AC-02: Regression and full tests, governance and exact-head protected publication pass.
