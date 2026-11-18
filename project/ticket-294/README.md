# Ticket 294: Bound operational list views with pre-built SQLite projections and crash-safe DAG wiring (#335)

- **ID**: ticket-294
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: user requested "wykonaj zalegle zadania https://github.com/semcod/planfile/issues" and "kontynuuj,scalaj"; resolves semcod/planfile#335 (`supports #334`) and addresses the crash-recovery inverse-edge finding from semcod/planfile#383 (`PR #387`) via protected Validator publication.

## Goal and scope

Pre-project operational list payloads into a dedicated SQLite `ticket_operational` table maintained during `rebuild()` and incremental `apply()`, read them from non-blocking read-only WAL snapshots, coalesce concurrent misses and repeated pollers over a bounded stale projection (`X-Planfile-Index-State: stale`, enforcing `413` byte bounds for oversized operational pages and `503` retryable responses instead of `500` on index contention), avoid `pf.list_tickets` model-cache retention in durable fallbacks, and make external blocker `blocks` inverse wiring in `DeliveryPlanRepository._materialize_unlocked` crash-safe across interrupted materialization replays.

## Acceptance criteria

- [x] AC-01: `SQLiteTicketIndex` maintains `ticket_operational` across `rebuild()`, `apply()`, and legacy DB upgrades, yielding byte-equivalent payloads to `_ticket_operational_payload` via non-blocking `?mode=ro` snapshots while concurrent writers hold SQLite locks.
- [x] AC-02: `/tickets?view=operational` (including `limit=1000`, `sprint=current`, `sprint=all`) serves the last complete pre-built index (`X-Planfile-Index-State: stale`) under index repair contention, coalesces identical misses (`_ticket_list_workload_slot` / `_TICKET_LIST_RESPONSE_BUILD_LOCKS`), caches stale bounded responses into `_TICKET_LIST_LATEST` with incremental FIFO eviction, and enforces `413 ticket_response_too_large` byte caps while honoring `require_fresh=true` (`503`).
- [x] AC-03: Durable list fallback `_durable_ticket_page_payload` streams raw `store.ticket_records` and instantiates Pydantic `Ticket` models only for the selected page without calling `pf.list_tickets` or populating `store._ticket_model_cache`.
- [x] AC-04: `POST /tickets` and `PATCH /tickets/{ticket_id}` degrade cleanly (`derived_index_degraded` / `X-Planfile-Index-State: degraded`) if `TicketIndexContentionError` happens after canonical commit instead of returning HTTP 500, and unhandled `TicketIndexContentionError` returns HTTP 503 `ticket_index_repair_pending`.
- [x] AC-05: `DeliveryPlanRepository._materialize_unlocked` reconciles `blocked_by` on already-persisted candidate tickets and wires inverse `blocks` edges for all `plan.candidates` so interrupted materialization replays never leave asymmetric cross-plan edges.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
