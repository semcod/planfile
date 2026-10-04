# Ticket 188: Queue GitHub completion events with durable recovery

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Owner**: agent:codex / codex-planfile188-oct4

SESSION_EXECUTION_AUTHORIZATION: user requested continuation, repairs, tests and protected merges. Source PLF-089 / semcod/planfile#194.

- [x] AC-01: Literal opt-in config queues exact routed done tickets after successful SDK/store/API mutations; default behavior remains local and performs no network request.
- [x] AC-02: Existing retry journal coalesces payloads, keeps newer revisions/cooldowns and reports delivery failures without claiming remote completion.
- [x] AC-03: Authorized worker recovers commit/enqueue crash gaps and manual completed-file edits across restarts; dry-run never mutates the queue.
- [ ] AC-04: Regression, full suite, real scoped canary, exact-head/base OneDev, independent protected merge and installed runtime verification pass.

Enable with `integrations.github.sync.enqueue_on_done: true` in the configured integration YAML (also writable through the typed configuration facade). Ticket must explicitly route to GitHub. Mutation only queues locally; run `planfile sync retry <project> --max-tickets 2` in an explicitly authorized worker to deliver. `--status` and `--dry-run` do not enqueue or publish. Disabling the option stops new completion enqueue/reconciliation; existing queue records still require an explicit retry worker. Restart recovery scans completed tickets within this one project, while remote delivery remains bounded by max-tickets. There is no new global daemon.

Validation: 12 regression failures reproduced before source implementation; 130 focused tests passed. Full suite: 1017 passed, 6 skipped. Ruff and native governance passed. Real scoped canary #224 was created once; local done event queued without network, controlled failure retained the cooldown, restarted native worker closed the same issue, and repeated worker invocation did not deliver again. Exact head/base OneDev and independent protected merge remain required.
