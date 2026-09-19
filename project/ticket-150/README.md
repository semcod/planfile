# Ticket 150: Adopt wellmanifest/new-project 0.20.32 managed package refresh

- **ID**: ticket-150
- **Owner**: codex-pilot17
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-19

## Goal and scope

Adopt standard `wellmanifest/new-project` 0.20.32 (`b6ba9c21a65a6a5648ecf904b64c3b75295e136f`) from previous revision `d54878a105a20d84dd554f205bc177dcacc8730a`.
Harmonize workstream configuration in `.governance/manifest.json`, bind standard and revision in `pyproject.toml`, refresh governance files, and verify zero drift.

## Acceptance criteria

- [x] AC-01: Standard adoption lock points to `0.20.32` (`b6ba9c21a65a6a5648ecf904b64c3b75295e136f`).
- [x] AC-02: `pyproject.toml` declares `standard = "0.20.32"` and `revision = "b6ba9c21a65a6a5648ecf904b64c3b75295e136f"`.
- [x] AC-03: Workstreams in `.governance/manifest.json` are aligned with canonical standard 0.20.32.
- [ ] AC-04: Full governance gate and unit tests pass cleanly.
