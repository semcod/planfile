# Ticket 271: bump goal to 2.2.9 to resolve dependency freshness gate

- **ID**: ticket-271
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-01

## Goal and scope

Upgrade locked package `goal` from 2.2.4 to 2.2.9 in `uv.lock` to resolve the repository-wide `freshness` check failure (Internal dependency freshness / PLF-21918).

## Acceptance criteria

- [x] AC-01: `uv lock --upgrade-package goal==2.2.9` updates `uv.lock` with latest published PyPI release 2.2.9.
- [x] AC-02: `goal dependencies --catalog .github/internal-dependencies.json --check` reports `fresh: true` and exits 0.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
