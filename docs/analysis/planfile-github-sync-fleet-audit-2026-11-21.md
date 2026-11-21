---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "planfile-github-sync-fleet-audit-2026-11-21",
  "kind": "analysis",
  "version": 1,
  "title": "Fleet audit of Planfile to GitHub synchronization drift (2026-11-21)",
  "status": "proposed",
  "owner": "semcod/planfile",
  "scope": "repository",
  "created": "2026-11-21",
  "updated": "2026-11-21",
  "review_after": "2026-12-05",
  "source_revision": "ac6273c108d28b9d725df891a5f11e7bcf7a2d86",
  "affected_repositories": [
    "semcod/planfile",
    "maskservice/c2004",
    "clonerd-com/app",
    "twinerd/premesh",
    "if-uri/urirun-contract",
    "dockuri/willuri"
  ],
  "evidence": [
    "https://github.com/semcod/planfile/blob/ac6273c108d28b9d725df891a5f11e7bcf7a2d86/docs/analysis/planfile-github-sync-policy.md",
    "https://github.com/maskservice/c2004/blob/main/scripts/planfile_github_drift.py"
  ]
}
---

# Analysis: Fleet audit of Planfile to GitHub synchronization drift (2026-11-21)

<!-- docs:section question -->
## Question

Are the local Planfile stores in every `~/github/*/*` checkout on the workstation
correctly synchronized with their GitHub repositories, and where they are not,
what kind of drift exists and who should resolve it?

<!-- docs:section scope -->
## Scope

All 879 primary checkouts under `~/github/*/*` that contain `.planfile/`
(hidden `.worktrees`/`.rescue` containers excluded). Non-history sprints only;
`history-*` snapshots are immutable copies. GitHub state was read once for
every mapped issue. Out of scope: writing any ticket, issue or retry record,
and judging whether an individual ticket should be open.

<!-- docs:section method -->
## Method

Phase 1 read local files only, with no API calls: `integrations.planfile.yaml`,
`github.planfile.yaml` and `config.yaml` for the configured repository,
`git config remote.origin.url`, `sync/github.state.yaml` (`repository`,
`ticket_map`, `synced_at`), `sync/github.retry.sqlite3`, and every sprint's
tickets (`.fast.json` mirror when current). Phase 2 compared each mapped
ticket with GitHub using batched GraphQL `issueOrPullRequest` aliases (about
100 per query, 1 point each) and listed the first 100 open issues per
repository. The whole remote phase cost about 35 GraphQL points. A ticket is
expected `OPEN` when its status is `open`, `in_progress`, `review` or
`blocked`, and `CLOSED` when terminal; this is the same rule as
`maskservice/c2004/scripts/planfile_github_drift.py`.

<!-- docs:section evidence -->
## Evidence

| Measure | Value |
| --- | --- |
| Checkouts with `.planfile` | 879 |
| No GitHub sync configured or used | 667 |
| GitHub sync configured or used | 212 (202 distinct GitHub repositories) |
| Configured but never synchronized (no `github.state.yaml`) | 82 |
| Last sync age, configured projects | median 46.3 d, p90 63.0 d, max 79.5 d |
| Last sync older than 7 days while active tickets exist | 118 projects |
| Tickets in sync-configured projects | 4,928 (1,827 active) |
| GitHub-integrated tickets without a mapping | 289 (259 active) |
| Mapped tickets compared with GitHub | 2,582 |
| In sync | 1,886 (73.0%) |
| Local open, GitHub closed | 250 tickets in 115 repositories |
| Mapped to a pull request instead of an issue | 442 in 24 repositories (164 in `clonerd-com/app`) |
| Local closed, GitHub open | 4 |
| Mapped issue missing on GitHub | 0 |
| Open GitHub issues without a local ticket (first 100 per repo) | 595 of 1,066 in 56 repositories |
| Retry queue not drained | 7 projects; `maskservice/c2004`: 2 failed, 1 pending, 6 running |
| Duplicate issue mappings | 6 projects |
| Configured repository differs from `origin` | `twinerd/premesh` → `subactor/premesh`; `if-uri/urirun-contract` (origin `dockuri/urirun-contract`) |
| Sync state repository differs from configuration | `dockuri/willuri` (state `paxlet-com/willuri`) |
| Scheduled fleet sync (`planfile-fleet-sync.timer`) | not installed |
| Repository-specific Planfile jobs | `c2004-planfile-autosync` and `fixos-planfile-sync` synchronize. `maskfleet-planfile-feed` exports a read-only snapshot. |

<!-- docs:section facts -->
## Facts

1. The [GitHub sync policy](planfile-github-sync-policy.md) makes outbound sync
   campaign-scoped and opt-in, so the 667 projects without GitHub sync follow
   the policy and are not drift.
2. Two repository-scoped timers run unattended synchronization. MaskFleet has
   a separate read-only snapshot feed. Most configured stores depend on
   explicitly initiated runs of `planfile sync github`. The measured activity
   is consistent with the 46-day median age and the 82 configured projects
   without a sync record.
3. The dominant real drift is one-directional: 250 tickets are still open
   locally after their GitHub issue was closed. Inbound state is not
   reconciled without a sync run.
4. 442 mappings point at pull requests, concentrated in repositories whose
   tickets were imported as `GITHUB-<n>` from a PR-and-issue listing. A pull
   request cannot carry the ticket lifecycle the policy expects.
   The current GitHub backend excludes pull requests from inbound issue
   reads by default. The `include_pull_requests` opt-in and stored legacy
   mappings need separate review.
5. Several `heyasa/*` and `paxlet-com/*` checkouts are clones of the same
   GitHub repository with separate stores. They report the same tickets twice,
   so per-repository counts above include that duplication.
6. All 202 GitHub repositories were reachable, none archived, and all have
   issues enabled. Missing data is not caused by access.

<!-- docs:section hypotheses -->
## Hypotheses

1. A bounded, state-only reconciliation of existing issue mappings could
   reduce drift in the 115 repositories with closed-remote tickets. The
   general `--direction from` operation can update local issue fields and
   import remote issues into Planfile. A state-only pilot needs an explicit
   selection of mapped tickets and an independently verified transition.
2. Extending mapping verification to every writer could prevent new
   `PullRequest` mappings. Existing mappings and repositories that explicitly
   include pull requests need an owner decision.
3. One canonical store per GitHub repository, instead of a store per clone,
   would remove the duplicated reports.

<!-- docs:section limitations -->
## Limitations

A single snapshot at 2026-11-20 23:00 UTC. Open issues were sampled to the
first 100 per repository, so "without a local ticket" is a lower bound;
unimported issues may also be outside a repository's intended scope. Titles
were not compared. The audit did not read the central Planfile API store,
which was in an index-rebuild livelock at the time (#403).

<!-- docs:section recommendations -->
## Recommendations

| Recommendation | Owner | Effect |
| --- | --- | --- |
| Qualify a bounded preview for opted-in repositories before scheduling state reconciliation | semcod/planfile maintainers and fleet operator | verifies eligible mappings and measures the API budget noted in #403 and dockuri/procache#18 |
| Review the 250 local-open/remote-closed tickets against current issue states and repository policy | each repository owner | identifies state corrections supported by fresh evidence |
| Reject `PullRequest` mappings at write time; review the 442 existing ones | semcod/planfile; `clonerd-com`, `semcod`, `wellmanifest` owners | prevents misleading mappings |
| Fix configuration mismatches (`twinerd/premesh`, `if-uri/urirun-contract`, `dockuri/willuri`) | those repository owners | sync writes to the right repository |
| Drain or resolve the `maskservice/c2004` retry queue (2 failed, 6 running) | maskservice/c2004 | completes queued deliveries |
| Map or drop the 259 active GitHub-integrated tickets without an issue | each repository owner | opt-in tickets reach GitHub |
