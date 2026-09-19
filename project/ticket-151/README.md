# ticket-151 — Adopt isolated procache

- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Owner**: codex:monag-triage-cache-20260919

SESSION_EXECUTION_AUTHORIZATION: execute cache corrections. Dependency adoption is the integration slice; transport retry is routed to a separate application ticket.

- [x] AC-01: Package and lock resolve merged procache f1548ef4.
- [x] AC-02: Dependency consistency, native requester smoke and full tests/governance pass.

Planfile PLF-078. Validation: 670 passed, 6 optional integration skips; dependency resolution and immutable procache pin verified.
