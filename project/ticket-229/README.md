# Ticket 229: Add ci_readiness: predict required-check failures, pin drift and cross-workstream deadlocks before a PR

- **ID**: ticket-229
- **Owner**: agent:antigravity (requested by the repository owner)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-19

## Goal and scope

Opening a pull request was the only way to learn which required checks would fail, and it took
hours to see why `main` could not be repaired: three independent faults (stale release metadata,
stale `uv.lock`, stale digests pinned by the protected verifier) each belong to a different owner,
and every required check must pass on every PR, so no single fix can merge. `planfile.ci_readiness`
is a read-only preflight that reports those facts in about 20 seconds:

- `release-metadata`, `dependency-freshness`, `verifier-pins` (`--verifier check-planfile.py`) and
  `governance` checks;
- each failing check names the path that fixes it and the workstream that owns that path
  (`.governance/manifest.json`), or `external` for another repository;
- two or more failures with different owners are reported as a `DEADLOCK` needing an owner
  decision, instead of being rediscovered by trial and error;
- an unavailable tool (for example `goal`) is `unavailable`, never a silent pass or a failure.

It edits nothing and grants no authority.

## Acceptance criteria

- [x] AC-01: Each check reports pass / fail / unavailable with detail and, on failure, a repair hint
  (`tests/test_ci_readiness.py`, 15 tests).
- [x] AC-02: Fixes owned by different workstreams, or by an external repository, are a deadlock;
  several failures with one owner are not.
- [x] AC-03: Exit code 0 only when every check passes and no deadlock exists; 2 for a directory
  that is not a repository; `--format json` is stable (`planfile.ci-readiness/v1`).
- [x] AC-04: On the real `main` (7354b47) with the real protected verifier it reproduces the
  manual diagnosis: release metadata 0.1.126 vs 0.1.127 (owner application), four stale internal
  dependencies (owner integration), `pyproject.toml` and `uv.lock` digests differ from the
  verifier pins (owner external), governance passes, verdict `DEADLOCK`.
- [x] AC-05: Governance gates pass.

## Not in scope

Fixing any of the faults it reports; hosted-only checks (it cannot run GitHub Actions); changing
the protected verifier or the workstream ownership model.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose and raw command
logs are not required delivery output.
