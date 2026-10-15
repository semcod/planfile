# Ticket 215: Prepare compact dedupe evidence outside mutation lock

- **ID**: ticket-215
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Planfile**: PLF-18410

## Authorization and scope

SESSION_EXECUTION_AUTHORIZATION: continue repairs, tests and protected merges. Follow up measured dedupe scan lock hold (3.337s cold, 2.406s warm). Build compact live dedupe evidence from authoritative YAML outside the mutation lock. Verify checksum and full source identity; under lock revalidate every current sprint and bound fallback reads. Preserve stable oldest selection, occurrence notes and cross-process uniqueness. Keep sharded behavior. PR260 deployment approval remains separate.

## Acceptance criteria

- AC-01: Warm dedupe scanning uses compact records; it does not decode unrelated full archives under lock. Retrieving/updating the matched ticket remains the existing storage path.
- AC-02: Replaced, added and changed sources cannot supply stale records; large cache misses fail closed under lock.
- AC-03: Closed records, ties, prefix labels, cache failures and concurrent same-key creates retain semantics.
- AC-04: Focused/full tests, governance, OneDev and independent exact-head Validator approve publication.

## Validation

Run tests/test_allocator_dedupe.py, tests/test_ticket_create_dedupe.py, tests/test_allocator_preparation.py and full pytest suite; isolated snapshot benchmark and protected CI. No production workload used by tests.

### Local results

Full suite: 1263 passed, 6 skipped (92.08s). Governance: zero errors/warnings; Ruff passed. Isolated HTTP snapshot: 73 sprint files, 456223022 YAML bytes, production mount read-only, journal/sync excluded. Baseline vs candidate mutation lock: create 4.155s vs 0.187s; first reuse 16.307s vs 12.270s; repeat reuse 2.288s vs 0.030s. Candidate cold request took 81.883s building authoritative evidence outside lock; first matching ticket retrieval still decodes existing storage. These concurrent-container measurements do not establish production throughput. Evidence: external planfile-dedupe-implementation logs. Protected CI and independent Validator remain required.
