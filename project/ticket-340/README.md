# Ticket 340: Fix URT campaign import dedup identity and stale preview re-verification

- **ID**: ticket-340
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-27

## Goal and scope

Address `semcod/planfile#478` (PLF-28988, follow-up to `#439` / CQRS-028 `#431`) inside `planfile/sync/urt_campaign_import.py` and `tests/test_urt_campaign_import.py`:
- Replace collision-prone `f"{campaign_id}:{proposal_id}"` concatenation with injective `build_urt_dedup_key()` (preserving exact colon-free legacy keys while encoding colon-containing pairs unambiguously).
- Preserve compatibility reading pre-change persisted state entries via verified embedded `(campaign_id, proposal_id)` identity without cross-matching colliding pairs.
- Re-verify live persisted state inside `commit_urt_campaign_import()` for `noop_duplicate`, `create`, and `supersede_revision` before writing state or emitting receipts, rejecting stale previews with `UrtCampaignRevisionConflictError`.

## Acceptance criteria

- [x] AC-01: Distinct `(campaign_id, proposal_id)` pairs never collide in `map_urt_campaign_item_to_planfile`, `prepare_urt_campaign_preview`, or `commit_urt_campaign_import`.
- [x] AC-02: Stale `noop_duplicate` (and stale `supersede_revision`) previews raise `UrtCampaignRevisionConflictError` during commit without modifying persisted state or emitting success receipts.
- [x] AC-03: Pre-change persisted states, plain legacy dedup keys, and verified GitHub receipt bindings remain compatible.
- [x] AC-04: Regression tests in `tests/test_urt_campaign_import.py` and `./project/governance-check.sh --base main` pass.

## Tracking boundary

This directory contains the minimal reviewed intent and acceptance criteria for `semcod/planfile#478`.
