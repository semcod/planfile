# ticket-236: Enable bounded, fail-open advisory ticket-radar enrichment for single and bulk direct ticket creation in issue #279.

- **ID**: ticket-236
- **Owner**: agent:coding-agent
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and scope

Direct ticket creation optionally appends a bounded advisory assessment using the existing local ticket-radar executable, while ticket persistence remains independent of radar availability and validity.

SESSION_EXECUTION_AUTHORIZATION: validated native ticket PLF-19711; Willman request eb23049b-d114-476c-81db-646b30fda77a; protected publication only.

## Acceptance criteria

- [x] AC-01: AC-01: Single and bulk creation through Planfile and Store persist validated advisory complexity, score, estimated minutes and split recommendation before generating new operational journal payloads.
- [x] AC-02: AC-02: Preserve the human description verbatim and append at most one advisory block of 512 characters; preserve existing producer advisory blocks without duplication.
- [x] AC-03: AC-03: Missing executable, process failure, timeout, excessive output, malformed JSON, unsupported schema, mismatched ticket identity or invalid metrics leave the description unchanged and never prevent otherwise valid creation.
- [x] AC-04: AC-04: Radar cannot change lifecycle, priority, execution, ownership, dependencies, acceptance criteria or delivery authority; existing tracker transport carries the advisory description without adapter changes.
- [ ] AC-05: AC-05: Both storage backends retain creation, deduplication, bulk allocation and journaling behavior; focused regressions, stack checks and the managed governance gate pass within the declared scope.

## Implementation evidence

- `planfile/core/store.py`: enrich descriptions in shared preparation before constructing new creation DSL; pass one five-second deadline through bulk preparation, including Planfile's unlocked entry points. Preserve supplied DSL and existing producer advisory blocks.
- `planfile/core/ticket_radar.py`: optional argument-vector invocation with JSON stdin and no output directory; one-second assessment deadline, bounded stdin/stdout handling, at most 65,536 retained output bytes, discarded stderr, and process-group cleanup on POSIX. Validate bundle/assessment schema identifiers, ticket identity and strict scalar metric types/ranges. Append only bounded Markdown metrics and the advisory disclaimer. Availability and invalid output never control persistence or execution.
- `tests/test_ticket_radar.py`: offline executable fixtures cover both YAML backends, optional SQLite index, public Store/Planfile single and bulk creation, journal payloads, deduplication, verbatim descriptions, producer blocks, invalid output, timeouts, output cap, stalled stdin, inherited pipes, bulk exhaustion and existing tracker payload construction. Authority tests compare all non-description fields and exclude private execution inputs from radar stdin.

## Validation evidence

Focused checks use the repository's existing `/home/tom/github/semcod/planfile/.venv/bin/python`. System Python lacks `ruff` and `procache` and its unrelated auto-loaded `pytest_aiohttp` fails import. No dependency installation or manifest change was made.

Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `-o addopts= -p no:wellmanifest_governance` only for these focused pytest runs: the user explicitly reserves the full governance gate and broad verification for the trusted runner after this turn. These focused results do not replace those gates.

- Final radar contract command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/tom/github/semcod/planfile/.venv/bin/python -m pytest -o addopts= -p no:wellmanifest_governance -q tests/test_ticket_radar.py`: **63 passed in 144.01s**. This includes the additional output-cap and descendant-cleanup cases and corrected timing measurements.
- Focused regression command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/tom/github/semcod/planfile/.venv/bin/python -m pytest -o addopts= -o faulthandler_timeout=30 -p no:wellmanifest_governance -q tests/test_ticket_create_dedupe.py tests/test_ticket_create_auto_sync.py tests/test_operational_dsl.py tests/test_sharded_yaml_storage.py::test_bulk_create_writes_each_affected_ticket_file_once tests/test_sharded_yaml_storage.py::test_bulk_create_rejects_over_limit_instead_of_silently_truncating -k 'not http'`: **27 passed, 1 failed, 1 deselected in 135.63s**.
- Failure: `tests/test_operational_dsl.py::test_ticket_dsl_redacts_nested_credentials` at line 43 expects the entire description to equal the redacted human URL. With `ticket-radar` available on PATH, the description also contains the intended advisory block. Redaction remains present; exact string equality fails because of the appended advisory. The test is outside the immutable allowlist. No production special case, test suppression or out-of-scope test edit was introduced to hide this mismatch.
- Ruff check of exactly the three material paths: PASS.
- `git diff --check`: PASS.
- An initial combined focused run was interrupted after prolonged lack of progress; the follow-up selection excludes the HTTP test. The follow-up's diagnostic stack showed a slow `os.fsync` in existing YAML persistence, so the interruption alone does not establish an HTTP defect. Two elapsed-time assertions were corrected to measure radar work rather than unrelated durable-store I/O; the implementation deadlines were unchanged.
- **Scope stop:** the known legacy assertion needs to account for optional enrichment, or the independent legacy regression environment must explicitly make the optional executable unavailable while radar-enabled behavior remains covered by the new tests. Editing that existing test requires a revised allowlist, which this turn cannot grant or modify. Implementation stopped on this evidence. AC-05 remains unfulfilled; the runner owns the authoritative full tests and managed governance gate, exactly once after this turn. No broad verification or todo2code workspace comparison was run.

## Retry and bounded handoff checkpoint

- Request: PLF-19711 / semcod/planfile#279; canonical ticket: ticket-236; workstream: application.
- Frozen accepted base and unchanged local HEAD: `2c48561341b9d120af170e00acd1b5fe7b809025`. Immutable `intent.json` retained byte-for-byte; raw SHA-256: `fe14ad0ea3af1df69cfc5754cee73484c02a7b5338137301dfc14d6c8ed47cdc`.
- Existing worktree: `/home/tom/github/semcod/planfile/.worktrees/ticket-236--project-job-eb23049b`; existing branch: `ticket/236-project-job-eb23049b`. Managed work-start admission returned `REUSE_EXISTING`, no blockers, one active ticket and no unchecked branches.
- Runner-owned lease observation: `ticket-236--project-job-eb23049b`, owner `agent:coding-agent`, session `allocation-ticket-236-2026-10-23T21:50:09Z`, lease revision `1`, fencing token `1`, expiry `2026-10-23T23:50:09Z`, matching branch and frozen HEAD. No renewal, takeover or release was performed.
- Existing runner continuity checkpoint resolved through `.governance/work_continuity.py`: `receipt:continuity.ticket-236.3.e2a26e71e8892b1db67fe81b11dc85fc9e38db3e3678a710a30380d5c4f33e5b`. Plan: `artifact:project-plan/eb23049b-d114-476c-81db-646b30fda77a`, SHA-256 `35a2181162710806cb53240059e4fac015c198340275fcca00f3fa93f7fd9813`; slice 1/1: `artifact:project-slice/eb23049b-d114-476c-81db-646b30fda77a`, SHA-256 `d9fc0059114bb26018ebd66ec774deafbb86d6d0d9163a44be9cb14d51f51b03`.
- Previous runner diagnostic: `project_session_git_observation_failed:exit_1:Aborting`. Read-only status, branch, HEAD and worktree observations succeeded in this retry. The failed command was not supplied; no claim is made to have repaired runner code. This implementation reuses the existing checkout without branch/commit/publication operations. Next action is the runner's reconciliation of the known validation/scope mismatch and exact Git observation before any authoritative validation/publication; no publication readiness is claimed.
- Scope: only the three allowed material paths and this ticket README were edited by this turn. The pre-existing `project/TICKETS.md` dirty projection and runner-created immutable intent were preserved. Dirty changes remain for the runner's snapshot/checkpoint and guarded commit; no external snapshot or publication receipt is fabricated here.
- Delivery states: scoped implementation and radar contract tests completed locally, acceptance validation incomplete because of the recorded regression/scope blocker; locally committed: no; pushed/PR opened: no; merged/deployed: no. Keep `IN_PROGRESS / PUBLICATION`; the trusted runner alone owns subsequent delivery effects and closure.
