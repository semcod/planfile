# Ticket 204: Bounded nonblocking autoupdate

- **ID**: ticket-204
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-07

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requests continuation, tests and protected merges; confirms no other writer remains on PR248. Accepted handoff preserves original3e639058 feature commit and resolves its missing implementation scope and canonical layout.

## Acceptance criteria

- [x] AC-01: Canonical worktree, own bounded lease and explicit scope for existing implementation.
- [x] AC-02: Cold-cache and opt-in upgrade dispatch are coalesced and bounded; optional caches fail quietly; focused tests pass.
- [ ] AC-03: Genuine full current-base OneDev passes and independent Validator approves/merges exact PR248 head.

## Validation

14 focused autoupdate tests plus14 CLI startup tests pass (28 total). Offline20-call cold-cache reproduction now dispatches once; independent SQLite connections coalesce concurrent callers without waiting. Opt-in upgrade has hourly reservation and300s pip child timeout. Cache publication is atomic; corrupt/busy/unavailable caches skip quietly. Pinned scope and governance/Ruff pass. Full protected OneDev verification and independent exact-head PR248 merge remain pending. No package upgrade was executed in this repair session.
