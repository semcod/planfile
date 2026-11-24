# Ticket 330: Preserve local dedupe:* labels during inbound external ticket sync

- **ID**: ticket-330
- **Owner**: agent:antigravity (SESSION_EXECUTION_AUTHORIZATION from user request)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-24

## Goal and scope

During inbound external sync (`_update_local_ticket` in
`planfile/sync/operations.py`), `update_fields["labels"]` overwrites the local
ticket's `labels` list directly with `ext_data["labels"]`. Because GitHub does
not carry local `dedupe:*` labels (e.g.
`dedupe:scheduled-route-health-and-canonical-qualification-v1`, which also exceeds
GitHub's 50-char label limit), inbound sync strips local deduplication markers
and breaks downstream consumers such as `validator-scheduled-route-health.service`.

Preserve any local `dedupe:*` labels when applying inbound external label updates.

## Acceptance criteria

- [x] AC-01: `_update_local_ticket` retains existing local `dedupe:*` labels not present in `ext_data["labels"]` while still applying remote label updates.
- [x] AC-02: Regression test `test_inbound_sync_preserves_local_dedupe_labels` in `tests/test_sync_inbound_resilience.py` and all existing `test_sync_inbound_sdk_revision.py` tests pass.
