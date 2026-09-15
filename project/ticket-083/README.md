# Ticket 083: Validate repository-local schema documents consistently

- **ID**: ticket-083
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: the owner requested continuation, repair,
testing, publication and protected merge during this session.

`planfile validate schema` must validate the document that belongs to the
selected repository. A repository using the current `.planfile/config.yaml`
contract must not be redirected to a parent checkout or fail because the
legacy root `planfile.yaml` is absent. Explicit legacy paths remain supported;
unknown or malformed local documents fail closed.

This ticket also makes `--file-type auto` distinguish planfile, sprint,
strategy and configuration documents. It does not change ticket sync,
configuration mutation or the unrelated dirty primary checkout.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [x] AC-02: Default validation selects only the repository-local contract and
  never a parent/global `.planfile` fallback.
- [x] AC-03: Auto-detection validates planfile, sprint, strategy and config
  documents against their respective contracts; explicit legacy paths retain
  their behavior.
- [ ] AC-04: Focused tests, full suite, governance and protected publication
  pass on the exact implementation head.

## Validation evidence

- Focused schema and CLI regressions: `22 passed`.
- Full Python suite: `544 passed, 6 skipped, 11 warnings`.
- Ruff import/unused checks on changed paths: passed.
- `git diff --check`: passed.
- Managed governance check on the accepted base: `GOV-PASS`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
