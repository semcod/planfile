# Ticket 279: Prevent bidirectional GitHub sync from reopening stale remote closures

- **ID**: ticket-279
- **Owner**: agent:codex-heyasa-audit
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-05

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested investigation and immediate
repair of Heyasa dependencies and Planfile/GitHub synchronization on 2026-11-05.
Coordination request: PLF-20370; parent workspace request: PLF-19975.

For `--direction both`, read GitHub before writing and reload the selected local
snapshot after inbound changes. The current outbound-first order can reopen a
remotely closed issue from a stale local open record. Preserve explicit one-way
semantics, exact repository/ticket/sprint selection, dry-run immutability and
native lifecycle guards. Do not force native blocked or terminal transitions.

## Acceptance criteria

- [x] AC-01: Session execution authorization and bounded scope recorded.
- [x] AC-02: Regression proves remote closure survives bidirectional sync and
  outbound uses the refreshed selected snapshot.
- [x] AC-03: Inbound failure prevents outbound effects; unrelated records and
  dry-run storage remain unchanged; native and legacy storage are covered.
- [ ] AC-04: Required checks and independent protected publication complete.

## Implementation and validation

The explicit operator decision on 2026-11-06 approved exactly this existing
allocation and its unchanged intent for a bounded initial source admission.
The deployed protected controller issued editing lease
`lease-c1b42dc54857ad048e6def49f710c7e6`, revision2/fencing838. Foreign ticket280
and its primary checkout files remain preserved. This receipt grants no merge
approval and no renewal or takeover.

GitHub both-direction synchronization now observes inbound first and reloads
the exact selected records. Native planning and live execution ownership stay
protected. Outbound uses detached payloads and exact raw snapshots, persists
only backend references through the existing CAS API and fails without
clobbering same-revision owner plans, notes or execution. Lifecycle conflicts
retain successful other receipts and prevent false full completion/comments.
Explicit one-way, non-GitHub and legacy behaviors retain their regression cases.

Native source tests:128passed,0skipped (93directregressions+35existing scope/identity controls) for test_sync_bidirectional_order.py and
test_sync_failure_status.py. Supplementary immutable-model tests also cover
existing scope/identity contracts. Ruff import organization is applied with
this repository's configuration. Required source governance and independent
publication remain separately verified; no required hosted/OS context waived.
Historical V1/V2 proposals were not applied unchanged.

Coordination: sourcePLF-20370/#339 and parentPLF-19975. Global managed-body and
outbound API persistence remain owned byPLF-20372/#341; this bounded CLI guard
does not claim that broader producer issue is resolved.
