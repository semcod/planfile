# Ticket 312: Pin subactor-procache to 853441c6 for ETag revalidation and rate-limit cooldown

- **ID**: ticket-312
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21

## Goal and scope

Update the `subactor-procache` dependency pin in `pyproject.toml` and `uv.lock`
from `94cb3118ede4a448a3cb2517e66a152687ff0af5` to the Validator-merged
`dockuri/procache` `main` commit `853441c623201517f293deb3f28a5195fc59de35`
(PR `#22` rate-limit cooldown per API family and PR `#23` ETag revalidation for
expired PyGithub reads).

## Acceptance criteria

- [ ] AC-01: `pyproject.toml` and `uv.lock` pin `subactor-procache` to
      `853441c623201517f293deb3f28a5195fc59de35` without unrelated lockfile churn.
- [ ] AC-02: Targeted GitHub/procache/index tests, `./project/governance-check.sh --base origin/main`,
      and `wellman check` pass cleanly.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
