# Ticket 170: Defer optional TestQL imports on Planfile SDK startup for Koru

- **ID**: ticket-170
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested continuing improvements in dependencies delaying Koru tasks, including implementation, tests and protected publication. Prior ticket169 is independently merged and released. reDUP005 is merged/released but its allocator and complete adoption are absent; preserve unrelated governance changes there.

Load optional TestQL integration exports only when a caller accesses them. Preserve exported function identity, signatures, discovery and existing helper behavior. Core Planfile and PlanfileClient operations must not eagerly load TestQL or its integration configuration. No ticket lifecycle, dependency manifest, routing, verification or production service changes.

## Acceptance criteria

- [x] AC-01: Fresh Planfile/PlanfileClient imports do not load TestQL integration/configuration; SDK still works.
- [x] AC-02: All four public TestQL exports remain discoverable and resolve to their original functions when requested; unknown attributes retain normal errors.
- [x] AC-03: Targeted tests, cold-process comparison against merged169, Ruff and managed governance pass.
- [ ] AC-04: Independently approved exact-head merge and isolated installed runtime integration with Koru; preserve global runtime.

## Validation

30 focused tests passed (8 fresh-process public API checks, 8 existing TestQL integration checks, 14 CLI startup/parity checks). Scoped Ruff, whitespace check and managed governance pass.

Five alternating fresh processes per version and command, using the same Python3.13 interpreter and source import roots: SDK import median1.393s ->0.585s (58.0% shorter); ticket help median1.466s ->1.048s (28.5% shorter), compared with the merged ticket169. Host load varies; this measures startup only, not whole Koru task duration. Public TestQL functions preserve identity and behavior. No paid requests or production queue mutations in these tests/benchmarks.

AC-04 remains pending independently approved publication and isolated installed runtime verification. Preserve global dependency/runtime configuration.
