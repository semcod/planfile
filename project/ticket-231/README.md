# Ticket 231: Move repository identity and cached YAML reads into foundation helpers

- **ID**: ticket-231
- **Owner**: agent:antigravity (requested by the repository owner)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-19

## Goal and scope

First repair ranked by `wellmanifest/streamline plan` for planfile: the foundation module
`planfile/project_paths.py` imported the sync layer (`planfile.sync.state.normalize_repository`)
through two function-level imports, a layer-direction and tier inversion hidden from import time.
It also carried a copy of the mtime-cached YAML reader that `sync/state.py` duplicates.

- `planfile/utils/repository.py`: `normalize_repository`, unchanged behavior, no planfile imports.
- `planfile/utils/yaml_cache.py`: `read_yaml_file` (the shared mtime-keyed cache).
- `planfile/utils/uri.py`: standard `uri('<uri>', [payload])`, `uri_jsonl(...)`, `render_uri_call_snippet(...)`, and `manage_uri_process(...)` linking scripts across languages (`python`, `bash`, `js`, `rust`, `go`, `php`) to `dockuri` URI processes (`DOCK-URI-001`, `DOCK-LFC-001`).
- `project_paths.py` and `sync/state.py` import both; `planfile.sync.state.normalize_repository`
  keeps working for its existing callers.
- `tests/test_sqlite_index_and_retry_perf.py` reads the cache from its new home.

## Acceptance criteria

- [x] AC-01: `project_paths.py` imports nothing from `planfile.sync` (test enforces it); foundation
  helpers import nothing outside `planfile.utils`.
- [x] AC-02: Callers share one implementation; normalization accepts and rejects the same inputs.
- [x] AC-03: Streamline on this branch: 51 -> 47 errors, no finding mentions `project_paths.py` or `planfile/utils/*`.
- [x] AC-04: `planfile.utils.uri` supports `uri()`, `uri_jsonl()`, `@file.jsonl`, polyglot snippets, and `proc://system/process/manage/v1` generation/modification/relocation.
- [x] AC-05: Governance gates pass.

## Follow-up (not in scope)

Three more copies of the cached YAML reader remain in `core/store.py` (reserved by ticket-226),
`core/configuration.py` and `integrations/config.py` (the latter deep-copies, so it is not a
drop-in). They can move to `planfile.utils.yaml_cache` in later tickets.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose and raw command
logs are not required delivery output.
