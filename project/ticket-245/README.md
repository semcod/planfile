# Ticket 245: Scope provider read caches and fence mutations

- **ID**: ticket-245
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-27
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — the user requested reusable caching for repeated API records across providers and investigation of missing coverage.

## Goal and scope

Isolate REST, OneDev and GitHub GraphQL records by their effective credentials, reuse the original procache backend, and fence old in-flight results after a mutation. Cache only verified query operations and valid successful responses.

## Acceptance criteria

- [x] AC-01: Repeated safe reads share results without crossing provider, account or representation boundaries.
- [x] AC-02: Provider regressions, invalidation races and managed governance pass.
- [ ] AC-03: Publication follows exact-head protected verification and independent approval.
