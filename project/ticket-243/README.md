# ticket-243: Keep atomic evidence independent of index rebuilds

- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION

SESSION_EXECUTION_AUTHORIZATION: user requests continued autonomous testing/fixing and protected publication. Parent PLF-17361; owner intake semcod/planfile:PLF-17347; Refs #297. User explicitly handed off the old ticket240/PR294 lease; the controller consumed exact old CAS and issued a strictly newer fence. Old process and source checkout remain untouched. Expired campaigns are not restarted.

## Goal and scope

Avoid index repair inside the atomic evidence mutation lock. Preserve source data, mutation locking and replay/idempotency. Source-only publication; runtime deployment is separate.

## Acceptance criteria

- [x] AC-01: A stale disposable ticket index held by another live process does not prevent atomic evidence append from reading authoritative ticket data.
- [x] AC-02: Duplicate and conflicting evidence keys, preserved outputs/input/execution and restart replay retain exactly-once semantics under index contention.
- [x] AC-03: The real mutation lock remains required; contention refuses boundedly without writing evidence or modifying another owner lock.
- [ ] AC-04: Scoped and full regression suites, governance and unchanged exact-head/base OneDev pass; independent Validator publishes the material fix.
- [ ] AC-05: Native deployment remains separate; preserve existing API process and evidence outbox until protected runtime integration qualification.

## Validation and continuation

The pre-fix reproduction failed in both flat and sharded storage under a live index-rebuild lock. After the bounded Store lookup change, all 73 evidence, index, writer-lock and concurrency tests pass; Ruff passes on both material files. The full local suite reports 1717 passed, 12 skipped and 6 failed. Five failures are independently reproduced on unchanged main (semantic advisory, operational path and CLI description behavior already repaired by pending PR #294). The remaining schema-output assertion is sensitive to terminal wrapping of the longer private checkout path; the same candidate test passes with COLUMNS=4096 (1 passed), while its initial wrapped-output failure remains recorded. No failing check is waived.

Protected publication waits for existing PR #295 / OneDev issue #715 dependency-input qualification and #294 integration. Preserve the exact source snapshot, existing API process and historical evidence outbox. Do not deploy this source patch by editing the live API package or deleting another process lock.
