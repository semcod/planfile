# Ticket 088: Make dependency freshness a reliable required PR gate

- **ID**: ticket-088
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested continuation of the
reported remediation work, including implementation, validation, publication
and protected merge. This ticket addresses only the freshness gate trigger;
repository branch protection is a separate external configuration step.

## Goal and scope

The repository declares `freshness` as a required status check, but its
pull-request trigger is path-filtered. A normal PR therefore has no freshness
check and cannot be safely covered by a required-check ruleset. Make the check
run on every pull request while retaining the existing scheduled and manual
triggers.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [x] AC-02: The `freshness` job runs on every pull request and remains
  available for scheduled and manual runs.
- [x] AC-03: The required-check declaration and workflow job name remain
  aligned, and the managed governance and stack checks pass.

## Validation evidence

- Workflow YAML parses with an unfiltered `pull_request` trigger and the
  `freshness` job is present.
- `./project/governance-check.sh --base origin/main --head HEAD --actor agent`:
  pass, 0 errors, 0 warnings.
- `uv run --no-sync python -m pytest -q tests`: 564 passed, 6 skipped, 1
  warning.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
