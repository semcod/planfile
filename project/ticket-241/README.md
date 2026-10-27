# Ticket 241: Update internal dependency goal to 2.2.4

- **ID**: ticket-241
- **Owner**: antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-24

SESSION_EXECUTION_AUTHORIZATION: the user authorized executing the remediation
plan to resolve internal dependency freshness for goal 2.2.4 and unblock PR gates.

## Goal and scope

Upgrade internal dependency `goal` in `uv.lock` from 2.2.1 to 2.2.4 so that the
required `freshness` status check passes on `main` and downstream pull requests.

## Acceptance criteria

- [x] AC-01: Scope is approved by the user execution authorization.
- [x] AC-02: `uv.lock` updates `goal` to 2.2.4 cleanly without extraneous dependency drift.
- [x] AC-03: `goal dependencies --catalog .github/internal-dependencies.json --check` reports fresh=true.
- [x] AC-04: `./project/governance-check.sh` passes cleanly (GOV-PASS).

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
