# Ticket 283: Preserve managed GitHub descriptions across round trips

- **ID**: ticket-283
- **Owner**: agent:codex-heyasa-audit
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-06

SESSION_EXECUTION_AUTHORIZATION: existing rootPLF-19975 audit/repair and explicit instruction to execute autonomously with existing consent, without repeated routine questions. Existing sourcePLF-20372/GitHub341 owns this request. Native279/282 are independently merged; foreign280 stays preserved. A genuine current protected controller grant is required before implementation.

## Goal and scope

Project only the unique machine-owned description on inbound; preserve remote-only prose and existing339local planning behavior. New managed creates use the owned region, explicit empty updates clear it, and ambiguous markers fail before mutation. Verify desired descriptions for actual outbound updates and receipt reuse; preserve mapped identity, lifecycle, raw snapshot and live execution protections. Legacy unmarked issues retain explicit import semantics. No mass historical edits, schema/dependency/signature changes or changes to foreign coreStore/allocator scope.

## Acceptance criteria

- [x] AC-01: Native behavior covers stable roundtrips, no human-prose import, empty updates, ambiguity, managed create/recovery and fresh/reused description verification, preserving identity/legacy and existing safeguards.
- [ ] AC-02: Ruff/governance, all8requiredchecks and independent exact-head publication succeed.

## Validation and publication

42 native description/receipt tests passed; 412 identity, CAS, raw-snapshot, live-execution and bidirectional regressions passed. The broad run passed807tests and exposed a poll fixture that patched stdlibtime globally, allowing storage waits to consume simulated pollticks. The fixture now patches only the watch dependency; its12tests pass. An obsolete redirect backend fixture now models its accepted body writes. Whole changed Python files pass Ruff; the managed gate passes. Final broad verification and all8independent publication checks remain required.

Native283 was rebound from925to926after an authentic cancelled/released handoff and fast-forward to the independently merged9abfd11f9d0c22c11ec2c5888d4c364682eb7885baseline. All foreign280bytes, implementation bytes, scope and original17:21:09UTC45minute ceiling are preserved. No source closure commit is authorized; retain IN_PROGRESS/PUBLICATION through trusted merge.
