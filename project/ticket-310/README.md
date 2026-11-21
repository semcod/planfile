# Ticket 310: Analyze fleet Planfile to GitHub sync drift 2026-11-21

- **ID**: ticket-310
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21

## Goal and scope

To be completed from human-owned input.

The owner asked on 2026-11-21 to check whether Planfile is correctly
synchronized with GitHub in all projects under `~/github/*/*`, and instructed
"kolejno wykonuj i testuj, scalaj" for the work in this session. This ticket
records the read-only audit as
`docs/analysis/planfile-github-sync-fleet-audit-2026-11-21.md` with its
`docs/README.md` index entry. No ticket, issue or retry record was written.

SESSION_EXECUTION_AUTHORIZATION covers integrating the current base, correcting the audit's descriptions of inbound sync and the MaskFleet feed, and protected publication.

Known gap: `wellmanifest/docs` `check.py --prepare` (revision
`b536d012cde20a27fbc9ff2b3dfc8c80bfc075a0`) accepts the placement but reports
the repository-level `DOCS_ADOPTION` finding (no tracked
`.governance/docs.json`), which belongs to the governance workstream.

## Acceptance criteria

- [x] AC-01: Scope is approved by a human owner.
- [x] AC-02: Measured facts with method and limits, hypotheses separated, an
      owner named for every recommendation.
- [x] AC-03: `docs/README.md` links the analysis.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

<!-- ticket-radar:start -->
## Ticket Radar

Initial planned-scope estimate; advisory only, not execution or merge approval.

| Measure | Initial assessment |
| --- | --- |
| Impact score | 56/100 |
| Complexity | M |
| Estimated effort | 47 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
