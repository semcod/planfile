# Ticket 256: Accelerate bounded safe YAML health analysis

- **ID**: ticket-256
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue user-requested Heyasa autonomy repairs, tests and independent publication. This is a disjoint CI dependency for native254 / PR314, whose frozen source116dc03 remains preserved. This native ticket256 is distinct from GitHub issue256 about scoped inbound reads.

OneDev job f15d356d52cb30441ce1e162 failed its Python3.11 coverage run solely at test_health_check_local_project_runs_promptly: HEALTH_TIMEOUT8s,1890other tests passed. Profiling the unchanged analyzer found614files/3.99MB taking7.8s undercProfile, with6.6s in PyYAML pure-Python parsing. Reuse safe accelerated loading, retain pure fallback and YAML semantics, and propagate TimeoutError through parser exception handling. Keep the8second CLI deadline and every required CI gate.

## Acceptance criteria

- [x] AC-01: Safe accelerated/pure loaders preserve issue/metric/task semantics for YAML1.1, GitHub workflow expressions, anchors, merges, Unicode, malformed and unsafe-tag inputs.
- [x] AC-02: Injected parser timeouts propagate to HEALTH_TIMEOUT rather than partial healthy output; no external command/tag executes.
- [ ] AC-03: Real repository health results match baseline; current affected checks, governance, protected verification and independent publication pass.

Native254 exact-owner resource was explicitly handed off after the failed CI receipt (releasedrev7/fence326); its branch and PR remain open/frozen. Never edit254 source or reset its OneDev attempts. After this dependency lands, resume254 against the changed base through fresh admission and verification.

## Validation

Owner-local Planfile tracking: PLF-20016 in semcod/planfile, allocated with a stable dedupe key. Two public-CLI timeout regressions failed before correction and now pass. All54affected tests pass with Testless coverage in7.50s; Ruff passes. Full615file/3.996MB analysis has byte-identical serialized issue/metric/task results with SafeLoader and CSafeLoader (digestb538eb9ca4cb641d2b4b16e10656428bc0bac7aa0febac8603393688390a767f). Latest unprofiled observations:1.964s pure,0.852s accelerated; timings are host observations, not a deadline guarantee. Exact module paths are asserted against this worktree before candidate profiling. Malformed YAML falls back to the original safe parser for identical error descriptions. The8second deadline, pure fallback and required checks remain. Protected verification/publication remain pending.
