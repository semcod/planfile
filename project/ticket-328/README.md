# Ticket 328: Qualify URTLog ticket identity by source repository

- **ID**: ticket-328
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-23

## Goal and scope

PLF-29385. Bind CLI ticket events and dependency references to the repository that owns the selected Planfile store. Keep historical unqualified records available by their original address.

## Acceptance criteria

- [x] AC-01 Two stores with the same ticket ID retain separate records, dependencies, and owners in one URTLog registry.
- [x] AC-02 Project-specific reads and the bounded D1 context return the selected ticket. The fleet summary identifies each project's scoped ticket.
- [x] AC-03 A successful CLI claim generates a lifecycle record. The bridge stays optional, and an unbound CLI store cannot use another repository's namespace.

The workspace owner requested persistent fixes to URI identity and increased URTLog adoption. The native SDK integration test exercises create, claim, depend, block and complete through the CLI. The central Planfile service reported its optional bridge disabled on 23 November.

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
| Estimated effort | 57 min |
| Planning budget | 30 min |
| Split recommended | yes |

Diagnostics: RADAR-ACCEPTANCE-MISSING, RADAR-BUDGET-EXCEEDED.
<!-- ticket-radar:end -->
