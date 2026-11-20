# Ticket 306: Retain the index locator across API worker restarts

- **ID**: ticket-306
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-20

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION is the request to continue, test and publish
through the independent Validator. This source slice supports the existing
[Planfile index recovery issue #313](https://github.com/semcod/planfile/issues/313).

When a worker observes a current index, retain its bounded locator in SQLite
metadata. Bind the write to the observed projection and reuse the locator after
a process restart only when the expected path and locator stamp agree. Keep the
conservative repair path when a matching snapshot is unavailable.

## Acceptance criteria

- [x] AC-01: After restarting against a stale projection and an untouched
  legacy archive, background repair can reuse the saved locator without reading
  the legacy archive. Current and archived ticket routing remain correct.
- [x] AC-02: A late observation cannot replace a newer locator. Unrelated
  locator removal still rebuilds to the canonical record on both YAML backends.

The focused test set passed 36 cases. In an isolated two-worker canary, the
original processes stopped before an archive write, then a fresh worker pair
restored all three discovery results without a full archive scan. The
canary used the current production image only as a dependency base and
mounted disposable data.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 64/100 |
| Complexity | L |
| Estimated effort | 61 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
