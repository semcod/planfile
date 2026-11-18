# Ticket 293: Extend verified repository placement and compose multi-repo delivery bundles (#383)

- **ID**: ticket-293
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: user requested "wykonaj zalegle zadania https://github.com/semcod/planfile/issues" and "kontynuuj,scalaj"; resolves semcod/planfile#383 (PLAN-001) with protected Validator publication after PR #386 (#384 / PLAN-006) merged.

## Goal and scope

Introduce versioned repository placement (`planfile.delivery-placement/v2`, `subactor.compiled-work-plan/v2`) validated against an explicit trusted target policy (`planfile.trusted-delivery-targets/v1`, covering `wellmanifest/*`, `subactor/*`, `semcod/*`, `dockuri/*`, `uritime/autodo`, and `paxlet-com/heyasa` with zero execution authority and anti-owner-aliasing checks) while preserving full read/validation compatibility for existing `v1` plans and adding explicit v1->v2 migration (`migrate_delivery_plan_v1_to_v2`). Keep the single-plan limit `<= 12` and single `(repository, accepted_base_sha)` invariant, and add deterministic multi-repo bundle composition and durable resumable materialization (`planfile.delivery-plan-bundle/v1`, `compose_delivery_plan_bundle`, `materialize_delivery_bundle`) that partitions large/cross-repo campaigns (such as `10 AUTO + 10 LLM + 10 HEY + 6 PLAN`) into bounded native subplans and maps cross-plan dependencies into real canonical `blocked_by`/`blocks` ticket edges without creating any execution grants, leases, or runner authority.

## Acceptance criteria

- [x] AC-01: Verified fixtures for `uritime/autodo` and `paxlet-com/heyasa` preserve real owner namespaces and exact `(repository, accepted_base_sha)` in `v2` while `v1` rejects unsupported placements, and untrusted targets or owner-alias mismatches fail closed before writes.
- [x] AC-02: All existing `v1` compiled plans and persisted state files remain readable/valid, and explicit `migrate_delivery_plan_v1_to_v2` preserves exact existing ticket IDs and split/dependency graph state.
- [x] AC-03: Candidate counts `12` vs `13` and full 36-proposal campaigns (`10 AUTO + 10 LLM + 10 HEY + 6 PLAN`) pass preflight deterministically partitioned into bounded groups (`<= 12` per subplan) with resolvable real `blocked_by`/`blocks` cross-repo ticket edges.
- [x] AC-04: Dry-run bundle materialization performs zero writes; replay materialization and restart resume after partial completion preserve exact ticket IDs, while conflicting digests/repositories/base SHAs or out-of-target dependencies fail closed.
- [x] AC-05: Verified foreign namespaces acquire `authority="none"` and `execution="inert"` with `executor is None` and zero execution leases, grants, or triggers.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
