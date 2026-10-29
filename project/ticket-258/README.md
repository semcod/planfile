# Ticket 258: Avoid ambiguous post-commit SQLite index contention

- **ID**: ticket-258
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-29

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: user requested continued autonomous repair, tests and protected publication ("kontynuuj, scalaj, testuj"). Continue parent PLF-20347 / Willman PLF-20340 and existing Planfile PLF-20365 / https://github.com/semcod/planfile/issues/316.

A durable ticket write must not report HTTP500 solely because the disposable SQLite index is busy/locked afterward. Record an atomic invalidation token visible to other workers, retain typed stale reads and normal rebuild recovery. Preserve CAS, source serialization and idempotent evidence. Propagate non-contention and pre-write errors. Existing issue313 owns rebuild liveness; issue317 owns qualified native runtime adoption. Preserve foreign governance worktree255.

## Acceptance criteria

- [x] AC-01: Real SQLite contention after authoritative upsert/delete/evidence write acknowledges success, another process rejects stale projection and a later rebuild recovers.
- [x] AC-02: Evidence replay, stale CAS, pre-write errors and unrelated SQLite errors retain their semantics.
- [ ] AC-03: Scoped checks and governance pass; protected current-base/head OneDev and independent publication are verified.

Validation: 142 scoped tests passed with Testless outcome accounting and coverage, including28 new regression cases. Ruff and managed governance passed. Real baseline/candidate canary: HTTP500 versus200 with the same committed value. Independent publication remains pending.
