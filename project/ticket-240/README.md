# ticket-240: Isolate generated ticket-radar advisory from semantic task content while preserving tracker output and correcting project-relative health assertions.

- **ID**: ticket-240
- **Owner**: agent:coding-agent
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and scope

Deliver semcod/planfile#293 within six application files: preserve enriched tracker descriptions, restore producer-independent semantic behavior, correct health-test path assertions, and verify through existing native OneDev and protected Validator publication.

SESSION_EXECUTION_AUTHORIZATION: validated native ticket PLF-19882; Willman request bb670545-dacf-4f80-9681-64ab82ac6000; protected publication only.

## Acceptance criteria

- [x] AC-01: Before implementation, native controllers revalidate ticket-238/PR292 terminal receipts, released ownership and fresh scope admission. Local evidence records PR292 merged at the accepted base, its lease released and no active registered writer. Preserve historical attempts; canonical allocation and fenced lease admission remain controller-owned.
- [x] AC-02: Preserve human descriptions verbatim, including empty text, bullets, Unicode, whitespace and human-authored advisory headings. Recognize only a complete generated advisory trailer for semantic exclusion; retain incomplete lookalikes and ordinary human text. Persist and publish the complete description with one bounded advisory, and keep enrichment idempotent.
- [x] AC-03: Duplicate detection, heuristic decomposition, LLM decomposition prompts and lexical/embedding coverage consume human task content. Ticket names and acceptance criteria retain their existing semantics. Results and model inputs remain identical with a valid optional producer present or absent, without changing thresholds.
- [x] AC-04: Deterministic valid producer fixtures exercise actual description enrichment without an installed host producer or external model. Run test_suggest_decomposition_from_bullets, test_suggest_decomposition_atomic_ticket and test_coverage_flags_uncovered_objective under producer-present and producer-absent conditions, preserving their original assertions and adding exact result comparisons.
- [x] AC-05: Preserve the exact bare-description assertion in test_reuse_appends_description_without_overwriting_original for producer absence. Add deterministic producer-present coverage asserting the exact human description plus exactly one expected advisory. Reuse preserves the complete original record except the existing permitted occurrence-note/history changes and invokes no second enrichment.
- [x] AC-06: Existing single/bulk persistence, journal, tracker-output, malformed-output, missing-producer, timeout and authority tests pass. Preserve the 512-character advisory bound, subprocess/output budgets and fail-open behavior. Advisory metrics never change scheduling, execution, review or merge authority.
- [x] AC-07: Correct health exclusion assertions to inspect directory components relative to the synthetic project. Add a project beneath an operational-looking parent, including .worktrees, and prove source files remain analyzed while actual operational directories inside the project remain excluded. Keep the analyzer and original Wellman checkout-bound fixture namespace unchanged.
- [ ] AC-08: Pass the original managed governance gate, relevant tests and full repository suite without skips, policy edits, dependency changes or fixture relocation. Protected publication requires fresh OneDev verification of the frozen head against current main and independent protected Validator approval. Keep machine-local paths in external receipts, tracked references repository-relative, and delivery states separately reported.


## Implementation evidence

The immutable intent remains bound to frozen base and unchanged HEAD
`e4b46fda131e4facf6c3945bc96633b3a6582939`.
Intent file SHA-256: `4992523f8905f1912b8c61171f44b7b1618c84823155cd5fd5e3c9065d19b4f8`.
Only this README and the six accepted material paths are edited by this turn.

- AC-01: Managed work-start reports `REUSE_EXISTING`, one active ticket, a
  canonical ticket-240 checkout, no scope blockers and local main/origin/main
  equal to the frozen base. Existing controller receipts record PR292 merged
  at that base and ticket-238's fencing token 15 released. Registered Git
  worktrees contain only the primary and this ticket checkout. The current
  allocation lease belongs to `agent:coding-agent`, revision 1, fencing token 1;
  it is neither renewed nor reclaimed by this model.
- AC-02: `ticket_radar._human_description` projects only the exact complete
  generated terminal advisory, searching at most the last 512 characters.
  It recognizes existing formatter output and validates the same scalar ranges.
  The producer, formatter and stored/tracker description remain intact.
  Exact persistence and repeated-preparation assertions cover empty, bullet,
  Unicode, whitespace and long descriptions. Human headings, incomplete or
  malformed lookalikes, and text following a block remain human content.
- AC-03: `semantic.ticket_text`, heuristic decomposition and the LLM prompt
  use the shared human-description projection. Ticket names, acceptance
  criteria, thresholds and authority retain their previous behavior.
  Producer-present/absent fixtures compare complete duplicate, heuristic and
  coverage results against human-only tickets. Local embedding/completion
  stubs assert exact human-only inputs and exact results, including empty text.
- AC-04: Before the production fix, the three original regression tests passed
  without a producer and failed with the deterministic valid producer:
  **3 passed, 3 failed**. Original semantic assertions are retained, with exact
  enriched-description assertions proving the present-producer cases run the
  real enrichment and validation path. No external model or binary is needed.
- AC-05: The original CLI reuse test keeps the exact `description == 'First'`
  absent-producer assertion. Its present-producer variant asserts the complete
  exact description and one advisory. Both assert one producer attempt, the
  original complete record including DSL, preserved history prefix, and only
  the expected occurrence output/history/timestamp changes.
- AC-06: Existing real subprocess tests continue to cover persistence, journal,
  malformed metrics, transport failures, stalled stdin, descendants, timeout,
  output limits, bulk budget and authority. Tracker payloads assert the full
  exact enriched description. Runtime bounds and enrichment are unchanged.
- AC-07: Health tests inspect project-relative path components and assert the
  exact analyzed source set. Parameterized parents include `.worktrees`,
  `.subactor` and `analyses`; actual operational directories inside every
  synthetic project remain excluded. The original checkout-bound fixture
  namespace and analyzer are unchanged; `.github` workflow analysis remains
  explicitly covered.
- AC-08: Original governance, the full repository suite, exact-head/current-base
  OneDev, independent protected Validator and guarded publication are assigned
  to the trusted runner after this model turn. They are not claimed as passed.
  No broad repository verification or todo2code compare-workspace is run here.

## Focused validation

Commands use the existing runner interpreter with
`-m pytest -o addopts='--tb=short'` so the repository's automatic broad
pytest governance plugin is not invoked during this bounded turn.
All listed test paths are repository-relative.

- Initial four-module check (`tests/test_semantic.py`,
  `tests/test_ticket_radar.py`, `tests/test_ticket_create_dedupe_cli.py`,
  `tests/test_health_check.py`): **129 passed, 1 failed**, 122.39 seconds.
  The failure was the existing real-time bulk-budget assertion requiring the
  first process to enrich within 0.35 seconds. The unchanged test passed in
  isolation: **1 passed**, 7.22 seconds. No deadline, threshold or assertion
  was weakened. The failed observation remains part of this evidence.
- Additional focused check of exact CLI reuse preservation and the expanded
  empty/bullet model-input cases: **6 passed**, 12.49 seconds.
- Ruff passes for `planfile/core/ticket_radar.py`, `tests/test_ticket_radar.py`,
  `tests/test_ticket_create_dedupe_cli.py` and `tests/test_health_check.py`.
  Baseline comparison confirms the remaining semantic-file findings predate
  this change: four in `planfile/core/semantic.py` (two import-layout findings,
  a duplicated stopword literal and non-strict zip) and one unused local in
  `tests/test_semantic.py`. New imports and zip calls were checked.
- Final four-module check on the completed implementation: **132 passed**,
  137.61 seconds, with no skips or deselections. This includes the original
  three semantic regressions in both producer modes and the unchanged
  real-time bulk-budget test that failed in the earlier observation.
- Final `git diff --check`: **passed**. Exact path inspection confirms only
  the six accepted material files and this README changed; the runner-created
  intent is preserved byte-for-byte, and acceptedBaseSha and HEAD still equal
  the frozen base. No commit, branch switch, push or PR operation occurred.

## Bounded handoff and delivery ledger

Ticket / plan / slice: ticket-240 / PLF-19882 / issue #293, one accepted slice.
Branch: `ticket/240-project-job-bb670545`; canonical linked ticket checkout.
Runner request: `bb670545-dacf-4f80-9681-64ab82ac6000`.
Observed lease session: `allocation-ticket-240-2026-10-24T11:34:39Z`;
revision 1, fencing token 1, expiry `2026-10-24T13:34:39Z`.
Previous durable runner checkpoint: ticket-240 sequence 3. Machine-local
receipt/snapshot locations belong in external execution evidence.
The trusted runner owns the canonical continuity stream, fresh snapshot,
lease fencing and all subsequent delivery effects.

- Completed: scoped implementation and 132 passing focused tests; authoritative
  full-suite/governance/OneDev/Validator and publication remain runner-owned.
- Locally committed: none by this model; HEAD remains the frozen base.
- Pushed / PR-open: no push or PR operation by this model.
- Merged / deployed: no merge or deployment by this model.

Keep **IN_PROGRESS / PUBLICATION**. Next action: the trusted runner observes
this exact dirty scope and immutable intent, takes its durable snapshot and
runs the authoritative gates once before any guarded publication.
