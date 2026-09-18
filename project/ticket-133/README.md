# Ticket 133: Harden GitHub outbound sync against API limits and invalid labels

- **ID**: ticket-133
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION (user requested concrete prevention changes across GitHub projects)

## Goal and scope

Add bounded GitHub outbound synchronization guardrails: validate and cache
labels before writes, throttle mutations, and stop a batch immediately when
GitHub reports a rate or abuse limit so a retry can resume safely.

The read cache is repository-scoped SQLite under
`PLANFILE_GITHUB_CACHE_DIR` (or the user's Planfile cache directory). It stores
only label names and marker-to-issue identities with TTLs; issue bodies, tokens,
and mutations are never cached.

## Acceptance criteria

- [x] AC-01: Scope is approved by the user's execution request.
- [x] AC-02: Invalid labels fail before any GitHub mutation.
- [x] AC-03: Rate-limit responses stop the current batch and retain receipts.
- [x] AC-04: Repeated label and marker reads use a repository-scoped TTL cache.
- [x] AC-05: Focused sync tests and the managed governance check pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
