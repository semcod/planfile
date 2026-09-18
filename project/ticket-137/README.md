# Ticket 137: Expose GitHub rate-limit retry hints to outbound callers

- **ID**: ticket-137
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: The user authorized implementation and
delivery continuation for the GitHub API traffic reduction workstream.

Implement the provider retry hint returned by GitHub rate-limit responses so
callers can schedule a safe retry without parsing provider exceptions.

## Acceptance criteria

- [x] AC-01: Rate-limit failures expose a bounded `Retry-After` hint when present.
- [x] AC-02: Absolute `X-RateLimit-Reset` responses are converted to seconds.
- [x] AC-03: Existing batch stop and durable receipt behavior remains intact.
- [ ] AC-04: Focused tests and the managed governance check pass.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
