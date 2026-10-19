# Ticket 227: Sync release metadata with the 0.1.127 release and stop hardcoding the version in its test

- **ID**: ticket-227
- **Owner**: agent:antigravity (requested by the repository owner)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-19

## Goal and scope

The ticket-220 release moved `pyproject.toml` and `uv.lock` to 0.1.127 but left
`planfile/release-metadata.json` at 0.1.126, so `tests/test_release_availability.py::
test_release_metadata_matches_published_offline_snapshot` fails on `main` and on every pull
request. PyPI already serves 0.1.127 with `requires_python >=3.10`, so the metadata is brought to
that observed state. The test also repeated the release number as a literal; it now reads it from
`pyproject.toml`, so the next bump cannot break it again.

## Acceptance criteria

- [x] AC-01: `release-metadata.json` source, runtime and published versions equal the version in
  `pyproject.toml` (0.1.127); `check(root, offline=True)` is `ok`.
- [x] AC-02: The test derives the expected version from `pyproject.toml` (no literal).
- [x] AC-03: `tests/test_release_availability.py` passes (2 passed).
- [x] AC-04: Governance gates pass; full suite 1280 passed, 6 skipped.

## Not in scope

`onedev/local-verify` fails with `PLANFILE_DEPENDENCY_PIN_MISMATCH` because the protected
`subactor/onedev-agent` check pins the digests of `pyproject.toml` and `uv.lock` from 2026-09-19.
That control lives in another repository and is not changed here.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose and raw command
logs are not required delivery output.
