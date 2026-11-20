# Ticket 307: Skip the full identity scan for proven locator additions

- **ID**: ticket-307
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION is the user request to continue autonomous delivery repairs and publish through the independent Validator. This slice supports [Planfile issue #313](https://github.com/semcod/planfile/issues/313).

In one live sample, restoring and comparing locator metadata took under a second, but reading all 29,083 projected identities took about 16 seconds. The repair time budget is 8 seconds. The locator gained a single entry in the changed daily history.

Use a validated prior locator for additions into changed sources and retain the existing verification for other locator changes.

## Acceptance criteria

- [x] AC-01: Cold repair handles a proven locator addition without reading the entire identity projection.
- [x] AC-02: Locator removals and remaps, archive precedence and shard rotation keep their verified behavior.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 52/100 |
| Complexity | M |
| Estimated effort | 51 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
