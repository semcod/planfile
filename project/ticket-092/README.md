# Ticket 092: Validate discovered repository-local .planfile configuration

- **ID**: ticket-092
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

## Goal and scope

Lock the repository-bounded schema selection already present on `main` with
offline regressions. Validation must prefer the current repository's
`.planfile/config.yaml`, keep an explicit root `planfile.yaml` fallback, and
refuse to read a parent or global store. The tests also verify that validation
is read-only and that the local config contract agrees with schema validation.

## Acceptance criteria

- [ ] AC-01: Local config takes precedence over a legacy document and validates
  successfully through the CLI and schema validator.
- [ ] AC-02: A child directory with only a parent/global `.planfile` fails
  closed without creating or mutating a store.
- [ ] AC-03: An explicit root legacy `planfile.yaml` remains supported.
- [ ] AC-04: Offline regression tests pass without network or external effects.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

## Limits

This ticket adds regression evidence for the implementation merged in
`34bd57f4ed91302f77e4c79dc7228173e9af3a04`; it does not alter discovery code
because the primary checkout contains unrelated dirty changes in those same
paths. GitHub sync identity and atomic publish are covered by tickets 084 and
090 respectively.
