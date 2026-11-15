# Ticket 284: Reconcile in_progress status with live leases/worktrees and export canonical executable queue

- **ID**: ticket-284
- **Owner**: agent:antigravity-aut14
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-15
- **Issue**: semcod/planfile#346

SESSION_EXECUTION_AUTHORIZATION: Authorized autonomous implementation, validation, and protected publication for AUT-14 (`semcod/planfile#346`) inside canonical worktree `.worktrees/ticket-284--reconcile-in-progress-executable-queue`, preserving foreign untracked `project/ticket-280/` untouched on primary checkout.

## Goal and scope

1. Implement a target-repository-aware `in_progress` reconciliation engine (`reconcile_in_progress` / `reconcile` Python API and CLI commands `planfile reconcile` / `planfile ticket reconcile`):
   - Verify `.git/new-project/terminal-receipts.json` (`outcome == "merged"` with Git ancestry on target branch) and landed merge commit receipts, transitioning verified merged `in_progress` tickets to `done` with recorded `terminalReceiptRef` and `terminalSha`.
   - Retain `in_progress` when bound to a live non-expired `.subactor/leases/*.json` lease, active worktree with uncommitted or ahead-of-target commits, or live `execution.lease_expires_at`.
   - Return abandoned `in_progress` tickets (no live lease and no active worktree) to `open` (`execution.state = "ready"`, clearing stale assignment/lease fields) atomically under `--apply` (`mutation_lock` + `expected_updated_at` CAS), defaulting to dry-run reporting.
   - Preserve tickets whose target repository checkout cannot be observed locally as `unobserved` without guessing or mutating.
2. Export one canonical executable pending queue specification and evaluator (`EXECUTABLE_QUEUE_SCHEMA = "planfile.executable-queue/v1"`, `is_executable_candidate`, `evaluate_executable_candidate`, `executable_queue`, `fleet_executable_queue`, and CLI commands `planfile executable-queue` / `planfile ticket executable-queue`) shared across Planfile, Heyasa, and `monag`.

## Acceptance criteria

- [x] AC-01: `reconcile_in_progress` / `planfile reconcile` closes verified merged `in_progress` tickets with `terminalReceiptRef`/`terminalSha`, resets abandoned `in_progress` tickets without live lease or active worktree to `open` under `--apply` (dry-run by default), and preserves locally unobservable target repositories as `unobserved`.
- [x] AC-02: Canonical `executable_queue` / `is_executable_candidate` (`planfile.executable-queue/v1`) evaluates open/ready status, non-blocked autonomy state, resolved `blocked_by` across active and archived history, valid target repository, and absence of active non-expired leases.
- [ ] AC-03: Unit/integration tests, Ruff, `./project/governance-check.sh`, and independent exact-head Validator publication pass.

## Validation and publication

7 new reconciliation and executable-queue tests plus 53 existing ticket execution and legacy dependency tests passed under `wellman run`; `mypy`, `ruff check`, `wellman check`, and `./project/governance-check.sh` passed with 0 errors. Retaining `IN_PROGRESS` / `PUBLICATION` through exact-head independent Validator approval and merge.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
