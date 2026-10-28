# Ticket 242: Record the seven baseline standard-pack adoptions with digest-bound evidence

- **ID**: ticket-242
- **Owner**: unresolved:human (willmux issue #307, owner repo semcod/planfile)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-24

## Goal and scope

willmux issue #307: `standard_pack_check.py` reported seven `STD-PACK-MISSING`
entries because `.governance/standard-adoption.json` declared no adoptions.
The levels themselves are already decided by the `baseline` profile in
`.governance/standard-packs.json`; the repository only lacked the adoption
records and their digest-bound evidence.

This ticket records the seven adoptions at their profile-required levels,
using the repository's **own** pinned standard (`manifest.lock.json`:
`wellmanifest/new-project 0.20.32 @ b6ba9c21…`) and the current managed
projection digest as evidence. No managed file, pin or hash is edited.

## Acceptance criteria

- [x] AC-01: SESSION_EXECUTION_AUTHORIZATION recorded in `ai-opencode.md`.
- [x] AC-02: Seven adoption records exist with model/level within the catalog's execution-model limits.
- [x] AC-03: Every record carries S0..level evidence with a valid sha256 and an artifact digest that matches the on-disk projection.
- [x] AC-04: `standard_pack_check.py` reports `ok: true` with zero findings.
- [x] AC-05: `governance-check` passes.
