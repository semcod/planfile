# Ticket 297: Isolate ambiguous GitHub description markers per issue during inbound list_tickets

- **ID**: ticket-297
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: User explicitly instructed `"kontynuuj,scalaj"` to execute pending unblocked tasks from `semcod/planfile/issues` through independent Validator publication. Target issue: `semcod/planfile#400` (`semcod/fixos#170` / `PLF-21821`).

## Goal and scope

Isolate `ValueError("sync_github_description_markers_ambiguous")` per issue inside `GitHubBackend._list_tickets` in `planfile/sync/github.py` so a single historical GitHub issue carrying malformed or duplicate `<!-- planfile:description:start -->` / `<!-- planfile:description:end -->` markers is quarantined with bounded body-free diagnostics without aborting valid unrelated issues in the same repository during inbound sync (`planfile sync github --direction from` or `both`).

Preserve fail-closed behavior everywhere else: `_description_bounds`, `_description_text`, `_merge_description`, `_get_ticket`, `_update_ticket`, `_create_ticket`, `list_selected_tickets`, and `_search_tickets` remain fail-closed (no silent marker unwrapping or mutation of ambiguous issues, and `_recover_lost_create` preserves duplicate visibility). Quarantine count must not starve `limit`, and non-marker exceptions must continue propagating.

## Acceptance criteria

- [x] AC-01: `GitHubBackend._list_tickets` isolates `sync_github_description_markers_ambiguous` per issue with bounded body-free diagnostics (`quarantined_inbound_issues`, `quarantined_inbound_count`) while keeping single-issue/selected/search/mutation paths fail-closed and adding regression tests in `tests/test_github_sync_description_markers.py`.
- [ ] AC-02: Ruff, governance, required CI/OneDev gates, and independent exact-head Validator merge succeed.

## Validation

- Ruff check (`planfile/sync/github.py`, `tests/test_github_sync_description_markers.py`): `All checks passed!`
- Pytest targeted & sync regression suites (`test_github_sync_description_markers.py`, `test_github_description_roundtrip.py`, `test_github_sync_preserves_issue.py`, `test_github_deduplication.py`, `test_sync_receipts.py`, `test_sync_bidirectional_order.py`, `test_sync_inbound_deadlines.py`, `test_sync_watch_inbound_polling.py`): `148 passed in 299.07s (0:04:59)` on Python 3.13.12 (`GOV-PASS`).
- Pending final governance check, `wellman check`, GitHub Actions + OneDev local verification, and independent Validator exact-head merge.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose and raw command logs are not required delivery output.
