# Ticket 228: Refresh stale internal dependencies in uv.lock (clickmd, costs, goal) and drop orphaned lock entries

- **ID**: ticket-228
- **Owner**: agent:antigravity (requested by the repository owner)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-19

## Goal and scope

`Internal dependency freshness` fails on `main` and on every pull request:
`goal dependencies --catalog .github/internal-dependencies.json --check` reports `clickmd 1.1.15`,
`costs 0.2.0` and `goal 2.2.0` as outdated. The check prints its own repair, `uv lock
--upgrade-package clickmd==1.1.16 --upgrade-package costs==0.2.1 --upgrade-package goal==2.2.1`.
Re-resolving also drops the stale `pfix` entry (the dependency was removed from `pyproject.toml`
earlier) together with the packages only it required (ipython, pipreqs, bleach and similar).
Only `uv.lock` changes.

## Acceptance criteria

- [x] AC-01: `goal dependencies --check` on the new lock reports `fresh: true`
  (clickmd 1.1.16, costs 0.2.1, goal 2.2.1 current).
- [x] AC-02: The locked CI recipe (`uv sync --locked --extra dev`, pytest) on the new lock: Python 3.13
  1279 passed, 6 skipped, 1 failed (`test_release_availability`, fixed by ticket-227, unrelated
  to the lock). Python 3.10 locally: the five `tests/test_serve_restart.py` cases time out
  identically on the old lock (verified on a clean copy of `main`), so they are an environment
  property here and not a regression; hosted `test (3.10)` passes on PR #271.
- [x] AC-03: Governance gates pass.

## Notes

The digest of `uv.lock` is pinned by the protected local verifier in `subactor/onedev-agent`
(`PLANFILE_DEPENDENCY_PIN_MISMATCH`). That pin is stale since the 0.1.127 release already and must
be refreshed once, against the final `pyproject.toml` and `uv.lock` on `main`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose and raw command
logs are not required delivery output.
