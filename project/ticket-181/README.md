# Ticket 181: Verify and reconcile GitHub lifecycle before publishing sync receipts

- **ID**: ticket-181
- **Owner**: codex / user-authorized maintenance
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-03

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user requested recording the remaining
C2004 work, verifying actual GitHub issue synchronization and fixing Planfile
if it does not synchronize. C2004 PLF-2876 / issue #363 already owns the
remaining lifecycle defect; this native ticket binds its library workstream.

Observed source at installed 45cae956 and independently merged be044461:
GitHub create does not apply terminal state, readback omits lifecycle, and
successful receipts skip fresh remote readback. Current open-ticket autosync
was separately verified with a real C2004 PLF-2922 / issue #408.

The original owner left this ticket blocked before implementation. The user
handed it off on 2026-10-04. Native continuation preflight selected this exact
canonical relative worktree; the existing controller accepted the bound plan
and scope with fencing token 129 after cancellation/release of the narrower
fence 128. No competing implementation scope was overwritten.

Implemented GitHub lifecycle projection on create/dedup, fresh provider readback
on retries, same-issue drift reconciliation, and receipt failure/recovery history.
The existing blocked/failed-to-closed projection and tracker title/body ownership
remain unchanged. Legacy backends without lifecycle projection retain compatibility.

## Acceptance criteria

- [ ] AC-01: GitHub create and deduplicated create project native terminal
  states consistently with update without duplicate issues.
- [ ] AC-02: Remote lifecycle mismatch fails closed and never counts as a
  successful publish; repeat sync checks actual remote state.
- [ ] AC-03: Regression tests cover done/blocked/failed create, drift after a
  successful receipt, unavailable readback and compatibility with other backends.
- [ ] AC-04: Exact-base/head OneDev and independent Validator publication,
  followed by runtime adoption and a real scoped issue canary.

## Validation observations

- Before implementation, all 10 new lifecycle regression cases failed.
- Real scoped semcod/planfile#209 showed false success: local done, remote open.
- Candidate repaired that same issue, verified fresh replay and deliberate remote
  lifecycle drift, and reused its marker without creating another issue.
- Focused sync compatibility tests passed; final focused and full suites are
  recorded externally before protected publication.
- Remaining delivery: exact-head tests/OneDev, independent Validator review,
  protected merge, installed-runtime readback, and release of this owned worktree.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

## Accepted handoff 2026-10-04

The user explicitly handed off ticket-181 and primary ticket-179/180 carriers to this session for completion and preservation. Originals and hashes are archived externally; independently merged PRs #205/#207 prove the primary runtime source update. Reuse the already natively allocated canonical relative worktree and actual controller CAS/fencing before source edits. SESSION_EXECUTION_AUTHORIZATION covers tests, necessary dependent fixes and protected publication.

## Necessary receipt dependency

A later failed readback was discarded by receipt deduplication whenever the same payload had an older success. Scope now includes receipt history and its tests; the old fence was cancelled/released and the existing controller issued a new scope/plan-bound fence before implementation.
