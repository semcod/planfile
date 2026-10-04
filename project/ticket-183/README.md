# Ticket 183: Persist failed GitHub autosync and drain bounded retries

- **ID**: ticket-183
- **Owner**: codex / user-authorized Planfile continuation
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-04

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested "kontynuuj, scalaj, napraiwaj".
Existing Planfile PLF-097 / GitHub #201 owns failed implicit-create autosync.
The current CLI warns and retains the ticket, but stores no retry job when a
failure precedes backend publication. Preserve local creation and explicit
failure semantics; add durable state and bounded opt-in recovery.

## Acceptance criteria

- [x] AC-01: Persist a repository-bound job before authorized GitHub autosync;
  failures survive restart and appear in ticket show without raw credentials.
- [x] AC-02: Retry only due, exact-ticket jobs with bounded batches, lease/revision
  fencing and Retry-After/backoff; newer edits cannot be cleared by an old worker.
- [x] AC-03: No-sync and dry-run cause no new delivery intent/network effects;
  changed routing fails closed and lost-response retries create no duplicate.
- [ ] AC-04: Tests, actual scoped GitHub canary, exact-head/base OneDev and
  independent Validator publication pass; installed runtime is verified.

The managed allocator reserved ticket-183. Canonical delivery uses the adopted
relative-worktree layout and the existing trusted controller with CAS/fencing.
No human-owned ticket files are created or changed.

## Validation evidence

- Full suite: 929 passed, 6 skipped; scoped Ruff and adopted governance pass.
- Focused retry/create tests: 30 passed, including two-worker exclusion,
  expired/replaced claims, newer revisions, cooldown and lost-response replay.
- Actual GitHub diagnostic: semcod/planfile#215. Implicit creation survived a
  controlled outage; a restarted worker delivered it, repeat did not create
  another Issue, and the same Issue was closed by terminal delivery.
- Private immutable evidence: planfile183-full-tests-oct4.log,
  planfile183-focused-tests-oct4.log and planfile183-live-canary-oct4.json.
- AC-04 remains pending exact-head/base OneDev, independent protected merge
  and installed-runtime readback. Tracker state is reconciled operationally;
  this ticket stays IN_PROGRESS / PUBLICATION through independent merge.
