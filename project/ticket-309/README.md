# Ticket 309: Optional uritime-urtlog bridge for planfile ticket lifecycle and dependency DAG

- **ID**: ticket-309
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-21
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION (autonomous pilot rollout of optional uritime-urtlog integration and publication)

## Goal and scope

Add a zero-mandatory-dependency, strictly opt-in `planfile.urtlog_bridge` module activated only when `URTLOG_STATE_DIR` is set and `urtlog` is importable:

- Project `planfile ticket create` (`kind="intent"`), `depend --after/--before` (`kind="intent"` DAG edge with `causation_id` & `depends_on`), and lifecycle transitions (`update`, `block`, `done`, `start`, `fail`, `complete`) into `UrtLogStore`.
- Index every ticket as `urn:planfile:ticket:<id>` in `UnifiedRegistry` with status, priority, dependencies, and block reason.
- Provide `load_planfile_queue_brief()` so Heyasa / Liquid D1 decision models immediately observe completed, blocked, and queued plan steps.

## Acceptance criteria

- [x] AC-01: Strict no-op when `URTLOG_STATE_DIR` is unset and fail-open when `urtlog` is absent; zero mandatory runtime dependencies.
- [x] AC-02: Live multi-ticket DAG (`create`, `depend`, `update`, `block`) projects into `UrtLogStore` and `UnifiedRegistry` and reconstructs via `load_planfile_queue_brief()`.
- [x] AC-03: Unit tests and `./project/governance-check.sh` pass cleanly with disjoint scope from active tickets.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
