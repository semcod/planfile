# Ticket 247: Admit comparative improvement findings as idempotent repository-scoped ticket DAGs

- **ID**: ticket-247
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the user authorized autonomous execution, testing,
and merging of open blocking tasks (`kontynuuj, testuj, scalaj, wykonuj zalegle`),
including `semcod/planfile` Issue #301 (`PLF-20328`, coordination `PLF-20321`,
deduplication key `cross-project-intent-improvement:2026-10-27:PLF`).
maxActiveMinutes: 60.

This ticket delivers the comparative finding-to-ticket lifecycle adapter in
`planfile/core/comparative_findings.py` and exposes first-class `blocked_by`,
`blocks`, `parent`, `children`, `group`, `acceptance_criteria`, and `files`
persistence plus `/findings/comparative/admit` in `planfile/__init__.py` and
`planfile/api/server.py`.

## Acceptance criteria

- [x] AC-01: Own the finding-to-ticket lifecycle adapter reusing
  `create_ticket_deduplicated`, current storage allocation, GitHub sync mapping,
  and `expected_updated_at` CAS preconditions.
- [x] AC-02: Bind stable deduplication keys to `(target_repository, capability,
  intent, policy_version)` plus material requirement fingerprints so refreshed
  evidence hashes append an occurrence rather than spawning a duplicate, while
  materially changed requirements remain distinguishable.
- [x] AC-03: Persist real `blocked_by` dependencies and `parent`/`children`
  relationships through supported Python and REST APIs (`TicketCreate`,
  `TicketUpdate`, and comparative finding admission) and validate DAG acyclicity
  and execution layers via `semcod/planfile-graph` (`planfile_graph`).
- [x] AC-04: Validate `SERVICE`/`FEATURE`/`BUGFIX` classification with reason,
  target scope, prerequisites, acceptance test, evidence freshness (rejecting
  obsolete target HEAD), rollback, and executor ownership with governance ticket
  allocation deferred until after Planfile admission.
- [x] AC-05: Validate twice-imported finding, concurrent refresh CAS, obsolete
  target HEAD, terminal ticket recurrence, sync idempotency, dependency failure,
  no-change (`intentional_difference_preserved`), and side-effect-free `dry_run`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
