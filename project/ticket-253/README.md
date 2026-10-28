# Ticket 253: Exact scoped GitHub inbound reads

- **ID**: ticket-253
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-10-28

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue user-requested Heyasa autonomy repair, tests and protected publication. Resume existing owner Planfile PLF-17304 / https://github.com/semcod/planfile/issues/256; no duplicate intake issue.

Read only canonical mapped GitHub issues before enumeration in selected inbound sync. Preserve repository identity, labels, CAS, active execution guards and existing unscoped/provider compatibility. This slice retains the remaining total-deadline/transport requirements of256.

## Acceptance criteria

- [x] AC-01: Selected mapped intake avoids unrelated enumeration, rejects invalid packets and preserves unrelated/concurrent work.
- [x] AC-02: Current scoped regression/compatibility tests and native governance pass.
- [ ] AC-03: Required current-head/base verification and independent protected publication succeed.

The original admission refusal is retained externally. Owner251 subsequently released its main lease at revision7/fence318; this session acquired a fresh main writer through the published controller. No ownership takeover or target/namespace substitution occurred.

The historical proposal8d7f716ee0e043e3f54fe306231e9fcdc8caafd066005f2c4625ef7f07722e88 was requalified on base4adc9a2:667affected tests including60selected-provider cases passed. Current base8e2b186 changes managed metadata only; functional inputs planfile/**, tests/**, pyproject.toml and uv.lock are byte-identical. These external fixture results grant no CI/review/deployment authority; fresh native validation remains required.

## Native validation

Actual admitted worktree:667tests across26affected test files passed with Testless coverage contexts in191.44s; Ruff passes; native governance passes with0errors/0warnings. One existing SQLite ResourceWarning is retained in the test log. Testless generated693external advisory suggestions; none were imported or published as tasks. No runtime dependency, required check or protected policy changed. AC-03 remains pending independent verification/publication.
