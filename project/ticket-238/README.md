# ticket-238: Persist canonical inbound priorities across legacy and typed imports, reject invalid evidence, and provide previewable CAS-protected legacy repair.

- **ID**: ticket-238
- **Owner**: agent:coding-agent
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and scope

Deliver semcod/planfile#278 within the six frozen application paths: canonical persisted inbound priorities, concrete diagnostics, regression evidence and a selected legacy repair preview/application boundary. Subsequent publication follows the existing protected native process; this planning response allocates nothing and performs no edits, commits, repairs or publication.

SESSION_EXECUTION_AUTHORIZATION: validated native ticket PLF-19275; Willman request 45a1b204-0d6b-438c-ae71-2efba4bf73df; protected publication only.

## Acceptance criteria

- [x] AC-01: Reproduce the omitted-priority legacy import and typed high-label default mismatch in regression fixtures linked to semcod/planfile#278 and paxlet-com/willman#298. Fixtures use synthetic records without modifying operational backlogs.
- [x] AC-02: One shared inbound boundary preserves valid explicit priorities, recognizes priority-high, priority:high, priority: high and priority::high formats, normalizes case and whitespace, maps medium and the existing med alias to normal, and uses the Ticket model default only when priority evidence is absent.
- [x] AC-03: Fresh legacy/V1, typed YAML and sharded imports persist an explicit canonical priority with identical semantics. Tests inspect physical YAML for field presence and value before checking fresh typed readback. Cover explicit values, high and medium labels, equivalent duplicate evidence and no evidence.
- [x] AC-04: Explicit priority survives dictionary extraction, TicketState transport and GenericBackend conversion without lossy coercion. Conflicting evidence, unknown values, empty supplied values and malformed types produce concrete diagnostics identifying the ticket and evidence. Rejected records acquire neither persisted mutations nor successful sync mappings; previews enforce the same rules.
- [x] AC-05: Inbound updates preserve existing local priority, including duplicate-import identity handling, regardless of changed remote priority evidence. This delivery introduces no authority to change existing scheduling priority through ordinary inbound updates.
- [x] AC-06: Provide an explicitly selected, previewable repair plan for imported legacy records missing raw priority. Preview reports selected IDs, evidence, proposed canonical values and diagnostics without writes. Explicit application uses PlanfileStore.update_ticket with the observed raw expected_snapshot, actor and reason under the existing store lock. Preserve lifecycle, execution, leases, ownership and sync references; retain normal audit history, reject stale snapshots and make repeat application a no-op. No remote completion publication occurs.
- [ ] AC-07: Existing repository-bound sync, selective filtering, lifecycle readback, terminal monotonicity and concurrency tests pass alongside new regression coverage. Monag validation, fleet admission and existing store safety checks remain unchanged.
- [ ] AC-08: Subsequent implementation uses a native scoped ticket and canonical fenced worktree after fresh ownership checks, preserving existing issue278 orchestration and failed-attempt records. Protected publication requires current-head OneDev verification and independent Validator approval. Report completed, locally committed, pushed/PR-open and merged/deployed separately; backlog repair never establishes execution completion.


## Retry 4 — implementation evidence

Request PLF-19275 / semcod/planfile#278 remains on runner-owned ticket-238.
The reported previous runner result was `project_plan_acceptance_invalid`.
The frozen intent is unchanged; each acceptance identifier appears once in the
checklist above and is mapped to concrete checks below. This turn supplies the scoped implementation and criterion-specific
regression evidence.
The runner must independently reassess its plan-acceptance result; this note
is not protected approval or evidence that its earlier error has cleared.

Frozen accepted base and unchanged HEAD:
`f24f8dea50d528fdf69d0b1a4b91c561410dfb15`.
Observed intent SHA-256:
`884d07fc5d8cee783a76d04671a98e99fad3a0f86946f81ae371d8cd0d4f5047`.
Only the six material paths in the immutable intent and this README are edited
by this model turn. The pre-existing `project/TICKETS.md` delta is preserved.

- AC-01: Before implementation, a synthetic `GITHUB-synthetic-298` import with
  `labels: [priority-high]` produced `raw_priority_present=False` and typed
  `priority=normal`. Source incident: [paxlet-com/willman#298](https://github.com/paxlet-com/willman/issues/298);
  producer fix: [semcod/planfile#278](https://github.com/semcod/planfile/issues/278).
  The persisted regression fixtures name both issues and use temporary stores.
- AC-02 / AC-03: `test_shared_priority_normalization` and
  `test_fresh_import_persists_priority_before_typed_readback` cover explicit
  canonical priorities, case/whitespace, all four supported label separators,
  medium/med aliases, equivalent evidence and absent evidence. The persistence
  matrix reads physical legacy, V1, typed YAML and sharded YAML before typed
  readback, asserting both field presence and canonical value.
- AC-04: `test_priority_evidence_survives_generic_typed_and_dictionary_transport`
  covers omission versus explicit null and malformed values. Diagnostic fixtures
  reject invalid or contradictory evidence, including dry runs, and assert no
  persisted record, successful mapping or misleading successful preview.
- AC-05: Legacy, typed-store and direct duplicate-identity update fixtures retain
  the existing local priority even when remote evidence is changed or malformed.
  Existing priority updates still require a separate authorized local operation.
- AC-06: Selected repair fixtures cover raw missing-field detection, write-free
  preview, explicit selection, diagnostics, store lock, exact snapshot CAS,
  actor/reason audit, stale/deleted records, repeated preview/application no-op,
  unselected records and lifecycle/execution/lease/owner/sync preservation.
  The repair helper invokes no remote backend or completion worker. The store's
  existing optional local completion enqueue policy remains unchanged.
- AC-07 / AC-08: Full-suite, governance, exact-head review and protected
  publication remain runner-owned. No Monag/fleet code or store safety gate is
  modified. Focused check results are recorded below when complete.

## Selected operational repair route (preview only unless separately applied)

Use `planfile.sync.priority.preview_priority_repair(store, selected_ids)` with
an explicit operator-selected list of imported record IDs. Inspect each
`plan.items` entry: ticket ID, sprint, evidence, proposed priority and diagnostic.
An existing raw priority is a no-op; missing/ambiguous identities, malformed
records, non-imported records or conflicting evidence block application of the
selection. A smaller valid selection requires a new preview.

For an explicitly authorized application, retain that exact plan and call
`apply_priority_repair(store, plan, actor=..., reason=...)`. It calls the ordinary
locked `PlanfileStore.update_ticket` with the observed raw `expected_snapshot`
and only a priority mutation. Each record has its own CAS; a multi-record plan
is not a transaction and stops on the first stale record. Re-preview before
resuming; repaired records then become no-ops. Reusing an old applied snapshot
fails CAS. No operational repair was run during this model turn.

Repairing backlog metadata establishes neither execution nor remote completion.
The historical ten-record repair cited by the issue is source context, not a
claim that this coding task executed against that backlog.

## Bounded continuation checkpoint

- Ticket / plan / slice: ticket-238 / PLF-19275 / issue #278; one frozen slice.
- Branch: `ticket/238-project-job-45a1b204`; worktree:
  the canonical linked checkout for `ticket-238`.
- Runner request: `45a1b204-0d6b-438c-ae71-2efba4bf73df`; allocation lease owner
  `agent:coding-agent`, session `allocation-ticket-238-2026-10-24T02:01:41Z`.
  Lease path: primary checkout `.subactor/leases/ticket-238--project-job-45a1b204.json`;
  observed revision 1, fencing token 1, expiry
  `2026-10-24T04:01:41Z`. This model does not renew, reclaim or release it.
- Work-start observation: `REUSE_EXISTING`, one active ticket, no scope blockers;
  local main and origin/main equal the frozen base. Remote/PR state is left to
  the runner; no network observation or external effect was performed here.
- Recovery: the primary checkout has three runner continuity events for this
  session. The linked checkout has no local continuity stream. Their intent digest and HEAD match this runner-supplied
  immutable intent and frozen base. They remain historical observations and do
  not certify the subsequently edited workspace or protected publication.
- Next action: runner-owned snapshot/checkpoint,
  authoritative repository gates and exact guarded publication. No commit,
  branch creation/switch, push or PR operation is authorized in this model turn.

## Delivery ledger

- Completed: scoped source implementation and focused regression evidence;
  authoritative runner validation remains pending.
- Locally committed: no commits created by this model turn.
- Pushed / PR-open: no push or PR operation by this model turn.
- Merged / deployed: no merge or deployment by this model turn.


## Focused validation results

Interpreter: existing repository `.venv/bin/python` (Python 3.13.12).
Focused pytest commands override `addopts` to prevent automatic governance
execution; authoritative broad checks remain assigned to the runner.
The first default pytest invocations incidentally loaded the repository's
`wellmanifest_governance` plugin and printed `GOV-PASS`. Those incidental
outputs are not claimed as the runner's authoritative validation. No full
repository test suite or todo2code compare-workspace was invoked.

- `python -m pytest -o addopts='--tb=short' tests/test_sync_legacy_operations.py tests/test_sync_inbound_sdk_revision.py -q`:
  **313 passed**, 61.50 seconds. These include the terminal-state and cache-free
  preview checks. Earlier radar-dependent fixture failures were resolved by
  comparing the entire pre-import concurrent record, strengthening preservation
  coverage without disabling the advisory or store guard.
- Scoped Ruff check on the six allowed material files: **passed**.
- `git diff --check`: **passed**.
- The initial compatibility attempt encountered a read-only default GitHub
  cache path, then stalled at the API completion TestClient fixture. The cache
  diagnostic was isolated to `test_create_ticket_rejects_pull_request_from_markers`
  (`OSError: Read-only file system`); a changed-environment rerun uses
  an isolated private `PLANFILE_GITHUB_CACHE_DIR` (machine-local path retained in the external execution evidence).
- Isolated API completion check: `timeout 20s ... pytest ... tests/test_sync_completion.py -k test_api_completion_uses_same_queue -vv`
  exited **124** while running the YAML variant; the sharded variant was not
  reached. Neither API variant has a passing result from this turn. The original
  stalled compatibility process was interrupted; it is not reported as passed.
  These API/server files are outside the frozen allowlist and remain untouched.

- Changed-environment compatibility command (same ten focused modules from
  AC-07, with `-k 'not test_api_completion_uses_same_queue'`, isolated cache
  and a 120-second process bound): **139 passed, 2 deselected**, 56.00 seconds.
  Covered repository binding, selective filters, state mappings, redirects,
  pull-request rejection, lifecycle readback, non-API completion, store
  concurrency, execution/terminal guards and priority weighting. The two
  deselected API variants correspond exactly to the isolated timeout above.

Handoff: implementation and focused checks are complete. Keep ticket-238
**IN_PROGRESS / PUBLICATION**. The trusted runner owns the fresh durable
snapshot/checkpoint, API/suite/governance verification and any subsequent
exact guarded publication. Local work is uncommitted; HEAD and immutable
intent remain unchanged. No remote backlog or completion was modified.
