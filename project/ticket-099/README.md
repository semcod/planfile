# Ticket 099: Publish Planfile release with automatic GitHub synchronization

- **ID**: ticket-099
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested implementation,
validation, publication and rollout of automatic Planfile/GitHub
synchronization across the participating repositories.

## Goal and scope

Publish Planfile `0.1.126`, the version pinned by the reusable synchronization
workflow, so calling repositories can install the exact workflow runtime.
Update the integration-owned package metadata and lockfile, build and verify
the distribution, and publish the release through the repository's supported
release boundary. The runtime module version is coordinated by dependent
application ticket-100, which owns `planfile/__init__.py`.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [ ] AC-02: `VERSION`, `pyproject.toml` and `uv.lock` consistently identify
  version `0.1.126`.
- [ ] AC-03: The source distribution and wheel build successfully and expose
  the expected package version.
- [ ] AC-04: The release is available from the configured package registry and
  the pinned workflow can install it.
- [ ] AC-05: Governance, package tests and protected exact-head publication
  checks pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
