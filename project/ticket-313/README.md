# Ticket 313: Split comma-separated labels in GitHubBackend._canonical_labels to prevent HTTP 422 sync failures

- **ID**: ticket-313
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21

## Goal and scope

GitHub's REST API rejects issue label names containing commas with `HTTP 422 Validation Failed: Label name invalid` (observed live in `fixos-planfile-sync.service` on tickets `PLF-21838`, `PLF-21839`, and `PLF-21840` carrying `memory,auto`, `tmp-cleanup,safety`, and `safety,defaults`).

Update `GitHubBackend._canonical_labels()` in `planfile/sync/github.py` to split comma-separated label strings into trimmed, deduplicated individual GitHub labels while preserving existing validation for empty, oversized (`>50` chars), control-character, and `dedupe:` / `priority: ` labels.

## Acceptance criteria

- [x] AC-01: Comma-separated labels such as `memory,auto` and `safety, defaults` are projected as distinct trimmed, deduplicated GitHub labels without losing `dedupe:` filtering or invalid-label rejection.
- [x] AC-02: `tests/test_github_sync.py`, existing GitHub sync/preflight tests, `./project/governance-check.sh`, and `wellman check` pass with 0 errors.
