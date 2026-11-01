# Ticket 270: Decide and establish scheduled incremental GitHub synchronization policy and tests

- **ID**: ticket-270
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-31

## Goal and scope

Document the architectural decision and policy governing outbound synchronization between the primary Planfile store and GitHub Issues (PLF-21789). The document formalizes campaign-scoped opt-in for outbound GitHub Issue creation, preserving ticket signal quality, bounded incremental processing, and idempotent resume from `.planfile/sync/github.state.yaml`.

## Acceptance criteria

- [x] AC-01: Document the explicit decision between scheduled incremental synchronization and campaign-scoped opt-in in `docs/analysis/planfile-github-sync-policy.md`.
- [x] AC-02: Establish idempotency invariants for resuming from `ticket_map` and respecting deduplication keys.
- [x] AC-03: Pass governance and Wellmanifest standards checks.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
