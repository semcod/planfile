# Ticket 230: Let one integration ticket own release metadata with the version it releases

- **ID**: ticket-230
- **Owner**: agent:antigravity (requested by the repository owner)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-19

## Goal and scope

A release changes the version in `pyproject.toml`, `uv.lock` and `VERSION` (workstream
`integration`), but `planfile/release-metadata.json` and `tests/test_release_availability.py` were
owned by `application` through the `planfile/**` and `tests/**` globs. The release ticket could
therefore not update them, and every release left `main` red on `test_release_availability`; fixing
it needed a second ticket whose pull request could not pass the other required checks.

This ticket lists those two paths in the `integration` workstream's `ownedPaths` in
`.governance/manifest.json`, so one integration ticket can carry the release and its metadata.

## Evidence

Checked in an isolated clone of `main` with this manifest as the base commit: one `integration`
ticket changing `uv.lock`, `planfile/release-metadata.json` and `tests/test_release_availability.py`
passes `./project/governance-check.sh` (`GOV-PASS`). Overlapping ownership with `application` raises
no finding; only changing the manifest inside the same ticket does, which is why this is a separate
`governance` ticket.

## Acceptance criteria

- [x] AC-01: `integration` owns the two release paths in `.governance/manifest.json`.
- [x] AC-02: An integration ticket touching `uv.lock` plus both paths passes governance when this
  manifest is the base (isolated-clone check above).
- [x] AC-03: Governance gates pass on this branch.

## Not in scope

The managed `.governance/manifest.base.json`, the adopted standard, and the protected verifier.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose and raw command
logs are not required delivery output.
