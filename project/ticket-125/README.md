# Ticket 125: Stop the outbound sync deleting issue content and resurrecting closed issues

- **ID**: ticket-125
- **Owner**: agent
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-17

SESSION_EXECUTION_AUTHORIZATION: on 2026-09-17 the owner asked to keep working
the prioritised list of improvements; this is its first item. GitHub allocation:
issue #125.

## Goal and scope

Two incidents on 2026-09-16, both from `planfile sync github --direction to`:

- `semcod/fixos#46` lost 28 lines — the failing `uv lock --check` evidence with
  commits and exit codes, two named governance blockers, a private receipt
  reference with its sha256 — because the sync replaced the issue body with the
  four-line ticket description. Its title lost the date, from
  `Kontynuacja 2026-09-15: relock uv.lock…` to `Kontynuacja: relock uv.lock…`.
- `subactor/onedev-agent#395` was reopened 70 seconds after a merged pull
  request closed it, because the local ticket was still `open`:

  ```
  closed    2026-09-16T11:54:18Z  ifuri-validator-agent[bot]   # merge of #396
  reopened  2026-09-16T11:55:26Z  tom-sapletta-com             # sync
  ```

An issue body accumulates discussion, evidence and decisions from everyone; a
ticket description is the local planning record. Treating the ticket as
authoritative for the whole body deletes other people's work with no diff, no
confirmation and no backup, and deriving the open state from ticket status
undoes a closure the tracker already recorded. In a repository where a bot
closes issues on merge, every agent that touches a ticket undoes those closures.

## What this ticket does not change, and why

The reopen stays. `ticket-101` widened it to `triage`, `in_progress` and
`in-progress`, and `tests/test_sync_routing.py` asserts it literally —
`assert issue.edits == [{"state": "open"}]` for each active status, eleven
parametrised cases. Removing it would mean rewriting coverage that a pull
request merged hours earlier added on purpose, which is the owner's decision
rather than a side effect of this fix. The evidence and two candidate designs
are recorded on issue #125: either skip an issue GitHub closed as `completed`
by a merge reference, or stop deriving issue state from ticket status in the
`to` direction and report the divergence instead.

So this ticket delivers the body and title half, where nothing asserts the
destructive behaviour and the loss is unrecoverable.

## Overlap with ticket-082

`intent.json` declares `conflictsWith: ["ticket-082"]` because the worktree
guard refuses two IN_PROGRESS tickets claiming `planfile/sync/github.py`
without it. That ticket is finished, not running: its head `b25378f` is an
ancestor of `origin/main` and its pull request #106 is merged, but its
`README.md` still says `IN_PROGRESS` and its worktree
`.worktrees/ticket-087-sync-quality` was never cleaned up. The declaration is
therefore bookkeeping, not serialisation of live work. Closing that stale
ticket is the owner's call; I did not edit a sibling worktree that still has
uncommitted changes.

## Acceptance criteria

- AC-01: an update keeps every line of the existing body, writes the
  description into `<!-- planfile:description:start -->…:end -->`, replaces only
  that section on the next sync, preserves deduplication markers, and leaves an
  existing title untouched.
- AC-02: an unchanged description issues no edit at all, so a repeated sync is
  not a write.
- AC-03: the governance gate passes and the suite gains no failure. `main` at
  `fa7d60e` already fails 8 tests in `tests/test_oql_configuration.py` and
  `tests/test_project_paths.py`, verified on a clean detached checkout; this
  branch fails the same 8 and no others.

## Non-goals

- The inbound direction, credentials, CI policy, and `ticket-101`'s terminal
  status projection.
- The dry-run report, which still does not distinguish creating an issue from
  rewriting a populated one. Recorded in #125 for a separate ticket.
