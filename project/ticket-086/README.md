# Ticket 086: Reject nested `.planfile` project discovery

- **ID**: ticket-086
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **GitHub issue**: semcod/planfile#99

## Goal and scope

When an agent starts inside `.planfile`, Planfile must resolve the owning
repository root. It must never create or use `.planfile/.planfile` as a second
project store. Explicitly passing a path inside `.planfile` fails with a clear
remediation message, while auto-discovery from a sprint or event subdirectory
returns the outer project.

## Acceptance criteria

- [x] Auto-discovery from `.planfile/**` resolves the outer repository.
- [x] Missing stores discovered from an inner path initialise at the project
      root only.
- [x] Direct `PlanfileStore`/`Planfile` construction inside `.planfile` fails
      closed before any nested files are written.
- [x] Regression tests cover nested and normal paths.

## Delivery evidence

- `pytest -q tests/test_project_paths.py` — pending after rebase.
- `ruff check planfile/project_paths.py planfile/__init__.py planfile/core/store.py tests/test_project_paths.py` — pending after rebase.
- `./project/governance-check.sh` — pending after rebase.
