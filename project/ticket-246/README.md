# Ticket 246: Isolate legacy GitHub metadata cache accounts

- **ID**: ticket-246
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-27
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — the user requested correct reusable caching for repeated provider API records.

## Goal and scope

Bind the existing durable GitHub metadata store to the effective account and API origin, so it cannot bypass the isolation already supplied by the lower HTTP cache.

## Acceptance criteria

- [x] AC-01: Same-account metadata is reused; different tokens and origins cannot read or clear each other's entries.
- [x] AC-02: Metadata regression tests, lint and managed governance pass.
- [ ] AC-03: Publication requires exact-head protected verification and independent approval.

Local verification: 36 scoped tests pass, with lint, managed governance and scoped testless coverage/planfiles. Required dependency freshness is independently owned by ticket-241; no lockfile or verification requirement is changed by this ticket.
