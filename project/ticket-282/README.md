# Ticket 282: Preserve accepted ticket intent when blocking execution

- **ID**: ticket-282
- **Owner**: agent:codex-heyasa-audit
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-06

SESSION_EXECUTION_AUTHORIZATION: user requested autonomous audit/repair and explicitly instructed execution with existing consent, without repeated questions. Parent PLF-19975; existing source PLF-20371 / GitHub #340. Separate disjoint scope from native279 and foreign280. Source editing requires a genuine current protected controller lease. Independent Validator owns approval/merge.

## Goal and scope

Preserve nonempty accepted descriptions through first and repeated block transitions. Keep reason history, explicit notes, inputs/outputs/artifacts and runtime claim termination. Retain existing synthetic description for originally empty tickets. No dependency, API signature or schema changes.

## Acceptance criteria

- [x] AC-01: Native regression proves nonempty/repeated description preservation, reason history and outputs, and existing lifecycle/empty-description compatibility.
- [ ] AC-02: Governance, all8required checks and independent exact-head publication pass.

## Validation and delivery

Native ticket execution regressions:40passed,0skipped. Ruff and managed governance pass. Tests preserve full accepted snapshots including advisory radar, reason history, repeated CLI blocking, outputs/artifacts and an actual legacy empty-description record. Existing #340 is the producer request. Independent8check PR publication remains pending; source279 PR342 is undergoing fresh CI at ee37a21e0118.

CI fixture correction: the running-claim test declares its accepted description explicitly, independent of advisory generation. The separate legacy-empty-record test remains. Native40tests, Python3.10.20 SDK lifecycle smoke, Ruff and governance pass; fresh protected matrix remains required.
