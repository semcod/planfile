# ticket-237: Maintain history ownership when tickets move or resume

- **ID**: ticket-237
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and authorization

Fix semcod/planfile#288: supported ticket moves and archived-ticket restoration maintain the history locator and its JSON mirror alongside ticket persistence. Keep the existing schema, public interfaces and dependencies.

SESSION_EXECUTION_AUTHORIZATION: explicit user request to continue, test and merge autonomously through Willman and protected publication. Native execution ticket PLF-19726; original Willman job a94841ec-fcc5-4049-9f7d-f28f6896b5ec. Independent exact-head approval remains required.

## Acceptance criteria

- [x] AC-01: History destinations record their owner; active destinations remove the mapping while preserving unrelated entries.
- [x] AC-02: Resume, ready and CLI resume restore unfinished archived tickets without reopening terminal tickets.
- [x] AC-03: Relocation and locator updates share the mutation lock, rebuild the JSON mirror and invalidate affected caches.
- [x] AC-04: Source-removal and locator-write failures roll back; if restoring the source also fails, retain the destination copy.
- [x] AC-05: Monolithic and sharded restoration regressions verify durable ownership independently of warmed caches, including SQLite readers.
- [ ] AC-06: Relevant storage regressions, lint and whole-branch governance pass; protected native CI validates the publication head and current base.

## Implementation

Store.move_ticket owns relocation and locator maintenance for both storage backends. The private locator helper preserves unrelated mappings and restores the previous locator on write failure. Ticket rollback restores the source before cleaning the destination, preserving a durable copy when rollback itself fails. Regression fixtures explicitly seed legacy stale ownership.

The material scope remains exactly planfile/core/store.py and tests/test_ticket_resume_archived.py: one component, no public interface changes and no dependencies.

## Accepted handoff and replan

The native runner created local commit 63720cf4504c0e8b4a349e7d51cb6d35ca0865e5 and failed GOV-DELIVERY-001 and GOV-PATH-001. That original commit is preserved in an external restorable Git bundle. After its orphan test was stopped, the authenticated process observer reported no owners and Willman's declared release preserved the ticket and worktree. The continuation acquired a new fenced controller lease under agent:codex.

Correct the invalid XS45 declaration to S45; the original outer plan was already S50. Keep every existing path and numerical implementation budget. Remove the obsolete read-only planning non-goal because the accepted session explicitly authorizes execution and protected publication. No protected policy or scope ownership changed. Replace machine-local README paths with portable commands.

## Validation

- Native author's focused archive/restoration selection: 51 passed in 37.56s; rollback follow-up: 22 passed, 13 deselected. The broader native four-module run was interrupted and is not a passing suite.
- Continuation lint: python3 -m ruff check planfile/core/store.py tests/test_ticket_resume_archived.py — PASS.
- Continuation governance: canonical managed Python entrypoint with explicit accepted base 4eaa4050c95a3c322e836bb30f09fafc2344f479 — PASS, zero errors and warnings. A default empty-diff pass is not used as whole-branch evidence.
- Separate double-failure reproduction verifies that both storage backends retain a durable ticket copy when locator persistence and source rollback both fail.
- Focused editing checks use pytest -o addopts= -p no:wellmanifest_governance; this avoids repeating the repository plugin during each focused run. The canonical full-branch governance check and protected CI remain mandatory.
- The continuation's broader seven-module storage selection is bounded and pending. The Willman system.command transport hit its own 30-second runner limit; that transport failure is not a test verdict. Test and publication receipts remain external.

## Delivery ledger

Implementation and local focused evidence exist. The continuation will amend the original unpublished material commit with the accepted plan and this portable record, then freeze the head. Push, PR, independent review, merge and deployment require their own observed receipts; none is asserted here in advance.
