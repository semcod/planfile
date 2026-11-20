# Ticket 300: CQRS-028: Map URT campaign metadata to Planfile and deduplicate import

- **ID**: ticket-300
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Workstream**: application
- **Origin**: semcod/planfile#431 (CQRS-028, P1) with SESSION_EXECUTION_AUTHORIZATION
- **Created**: 2026-11-19

## Goal and scope

Implement URT campaign metadata mapping, preview validation, revision-aware deduplication, and verified receipt binding in `planfile/sync/urt_campaign_import.py` with unit tests in `tests/test_urt_campaign_import.py`:
- Reject passing raw unmapped `BACKLOG.json` campaign manifests or raw proposals directly as native Planfile ticket payloads (`assert_not_raw_backlog_payload`).
- Separate `tracking_repository` (`semcod/planfile`) strictly from `target_repository_candidate`, normalizing missing/unknown/`nieustalone` routes to `target_repository_candidate=None` (`routing_status="unrouted"`) without guessing.
- Preserve original phrase, `urt_ref`, `temporal_intent`, `resolution_metadata`, `plan_revision`, `evidences`, and non-accepted `proposal_disposition` (`planned_backlog_item`, `accepted=False`) in structured metadata without collapsing intent into a bare timestamp or auto-accepted status.
- Deduplicate repeated prepares/commits by `f"{campaign_id}:{proposal_id}"`: identical semantic content returns `action="noop_duplicate"`; changed content without a higher `plan_revision` raises `UrtCampaignRevisionConflictError`; explicit `plan_revision` increments record `action="supersede_revision"` without deleting prior published records.
- Bind `linked_github_issue` exclusively from verified `planfile.sync.receipts` readback (`outcome="succeeded"` with numeric `remote_id`), ignoring unverified issue number hints and never fabricating IDs.

## Acceptance criteria

- [x] AC-01: Raw `BACKLOG.json` campaign manifests/items are rejected from direct native ticket ingestion without validated mapping.
- [x] AC-02: Repeating preview/commit of identical content produces zero duplicates (`noop_duplicate`); changed content under the same key requires `plan_revision > existing_revision` (`UrtCampaignRevisionConflictError` otherwise).
- [x] AC-03: `tracking_repository` remains strictly separated from `target_repository_candidate`, leaving unrouted/unknown candidates as `None` (`unrouted`).
- [x] AC-04: Original phrase, temporal intent/resolution metadata, and non-accepted proposal status are preserved cleanly without collapsing to a bare timestamp.
- [x] AC-05: GitHub issue references are attached only from verified succeeded sync receipts, never from unverified raw hints or fabricated IDs.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
