# Ticket 292: Unify version identity and close autonomy payload validation (#384)

- **ID**: ticket-292
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: user requested "wykonaj zalegle zadania https://github.com/semcod/planfile/issues" and "kontynuuj,scalaj"; resolves semcod/planfile#384 (PLAN-006) with protected Validator publication.

## Goal and scope

Unify package/runtime version identity (`planfile/version_identity.py`, `planfile/__init__.py`) so `pyproject.toml`, `planfile/release-metadata.json`, `planfile.__version__`, CLI `--version`, `/health`, and OpenAPI report consistent runtime identity across checkout and distribution installs alongside separate `source_sha`, deployment caveats, and schema capability maps; extend `planfile/release_availability.py` to catch runtime constant drift (`AC-02`) and explicitly qualify or block full/offline installs against non-portable VCS dependencies (`#303`/`#329`); close autonomy mutation/admission payload contracts (`extra="forbid"`, typed dependencies/booleans, schema versions, nested dict key rejection preserving partial PATCH semantics, and machine-readable `field_path` 422 responses) in `planfile/api/server.py` and `planfile/core/comparative_findings.py`; and strictly separate `autodo.planfile-import/v1` from native `subactor.compiled-work-plan/v1` and legacy Strategy compatibility boundaries in `planfile/delivery_plan_contracts.py` and `planfile/delivery_plan.py`.

## Acceptance criteria

- [x] AC-01: Checkout and distribution runtime `__version__`, CLI `--version`, `/health`, and OpenAPI report consistent version `0.1.127` with separate `source_sha`, `version_identifies_active_deployment: false`, and explicit `schema_versions`.
- [x] AC-02: `release_availability.check` detects deliberate drift between `pyproject.toml` and runtime `__version__` constants in `planfile/__init__.py` or `planfile/version_identity.py` while preserving legacy synthetic fixtures without package source files.
- [x] AC-03: Unknown fields, typos (e.g. `bloked_by`), nested unknown keys, wrong dependency/boolean types, and unsupported schema versions on `POST /tickets`, `PATCH /tickets/{id}`, and `POST /findings/comparative/admit` (plus `admit_comparative_findings`) fail closed before store write with machine-readable `field_path`.
- [x] AC-04: Explicit legacy Strategy YAML compatibility remains functional via `load_strategy_yaml`, while passing legacy Strategy payloads into native delivery-plan or comparative admission endpoints fails closed without silent downgrade or store writes.
- [x] AC-05: `preflight_delivery_plan` and `materialize_delivery_plan` strictly distinguish `autodo.planfile-import/v1` import metadata envelopes from native `subactor.compiled-work-plan/v1` and reject unknown fields via `extra="forbid"`.
- [x] AC-06: `release_availability.qualify_distribution_install` explicitly reports `qualified_full_offline_install: false` and `#303`/`#329` blockers for non-portable VCS dependencies (`subactor-procache @ git+...`) and never conflates minimal SDK imports with full offline install qualification.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
