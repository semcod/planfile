# Ticket 175: Avoid per-issue hydration during GitHub marker deduplication

- **ID**: ticket-175
- **Owner**: codex / user-authorized maintenance
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-01

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested fixing Planfile and dependencies
when defects prevent or slow C2004 refactoring delivery, with tests and protected merge.
Avoid per-issue network hydration while classifying list results during marker lookup.
No change to deduplication identity, open/closed ordering, PR exclusion or publication authority.

## Acceptance criteria

- [x] AC-01: Ordinary complete list payloads cause no per-issue hydration.
- [x] AC-02: Pull requests are excluded even when they contain a matching marker.
- [x] AC-03: Missing payload fields retain safe hydration/fallback behavior.
- [x] AC-04: Existing sync regression tests and managed governance pass.

## Evidence

Real PyGithub Issue objects with a mocked requester: regression failed with five
extra requests, then passed with zero. Partial PR projection still hydrates once
and is excluded. `python3 -m pytest tests/test_sync*.py tests/test_ticket_comments.py -q`:
126 passed. Local pytest governance preflight: GOV-PASS.
Independent exact-head publication remains required; no self-approval or bypass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
