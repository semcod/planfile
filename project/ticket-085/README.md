# Ticket 085: Bound health checks and parse GitHub workflow expressions

- **ID**: ticket-085
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

SESSION_EXECUTION_AUTHORIZATION: the owner requested that the reported fleet
problems be ticketed and repaired, with important reliability issues first.

## Goal and scope

Make `planfile health check` a bounded, read-only diagnostic. It must expose a
configurable file/time budget, return a structured result and nonzero status on
timeout or analysis errors, and avoid creating `.planfile_analysis` artifacts.
GitHub Actions YAML is a supported diagnostic input: YAML 1.1 parses the `on`
key as a boolean, so workflow analysis must normalize keys and report one clear
unsupported-construct diagnostic instead of a misleading duplicate parse error.

## Acceptance criteria

- [x] AC-01: Scope is approved by the owner's execution authorization above.
- [ ] AC-02: Health analysis enforces configurable max-files/max-bytes and a
  wall-clock timeout; timeout/error output includes the project path and exits 1.
- [ ] AC-03: `--format json` emits stable machine-readable status, counts and
  diagnostics; text output remains usable for interactive shell Markdown.
- [ ] AC-04: Workflow fixtures containing `${{ }}` and the YAML `on` key parse
  without the current `'bool' object has no attribute 'lower'` failure; a truly
  unsupported construct produces one diagnostic.
- [ ] AC-05: Focused tests, full suite, Ruff, `git diff --check`, governance and
  protected publication pass on the exact implementation head.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not delivery output.
