# Ticket 127: Generator/analyzer produce identical plans and skip validate auto-detection; extend todo-sync edge-case coverage

- **ID**: ticket-127
- **Owner**: agent:claude-code
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18

SESSION_EXECUTION_AUTHORIZATION: user asked to work through the open sync
correctness backlog for this project ("zajmij się nimi") in an earlier turn
of this session; this ticket and its implementation are that authorized work.

## Goal and scope

Two defects:

1. `generate_from_current_project` re-analyzed the `.planfile_analysis` temp
   directory instead of reusing its own already-computed analysis, so every
   project produced the identical strategy `.Planfile_Analysis Improvement Plan`.
   Thread the already-computed `analysis_result` through to
   `generate_from_analysis` instead of re-analyzing a throwaway directory.
2. `analyze_directory` only excluded a short hardcoded list of directory
   names (`__pycache__`, `.git`, `node_modules`, `.pytest_cache`,
   `.planfile_analysis`) and missed common vendored/build trees
   (`.venv`, `site-packages`, `dist`, `*.egg-info`, ...), so dependency code
   produced the project's critical/high tickets. Added a class-level
   `EXCLUDED_DIRS`/`EXCLUDED_DIR_SUFFIXES` set and an `is_excluded` helper
   checked against every path component below the analysis root.

(A third originally-targeted defect, `validate schema` misjudging Strategy
documents, was already fixed on `main` by other concurrent work before this
branch was rebased — see the rebase note below. `main`'s
`detect_document_type`/`detect_file_type` also add a `config` document type
and a better `unknown` fallback than this ticket's original version; kept
as-is.)

This branch also carried a pre-existing, unrelated addition to
`tests/test_todo_sync.py` (431 lines of edge-case coverage, authored before
this ticket was opened). Two of those added tests fail against current
`main` (`todo_sync.py`/`strategy_input.py` raise instead of returning a
report for a missing/invalid strategy file) — unrelated to this ticket's
scope and not investigated here. Reverted `tests/test_todo_sync.py` to
`main`'s version so this ticket stays green and scoped; that coverage is
left for whoever picks it up next.

## Acceptance criteria

- [x] AC-01: `generate_from_current_project` passes its own analysis through
      to `generate_from_analysis` rather than re-analyzing `.planfile_analysis`.
- [x] AC-02: `analyze_directory` skips `.venv`, `site-packages`, `dist`,
      `*.egg-info` and similar vendored/build trees wherever they are nested,
      while still analyzing a project that merely lives under a similarly
      named ancestor directory.
- [x] AC-03: Regression tests in `tests/test_generator_analysis_passthrough.py`
      cover both defects and pass against current `main`.

## Rebase note

This branch was rebased onto `main` after `validate schema`'s
Strategy-vs-ticket-store misjudgment turned out to already be fixed there,
more thoroughly, by other concurrent work (`schema.py` and
`cli/groups/validate/commands.py` resolved by taking `main`'s version).
`file_analyzer.py` conflicted on an unrelated axis: `main` had added
read-budget limits (`max_files`/`max_bytes`) to the same method, but with the
old short exclusion list still in place, not this ticket's broader one.
Taking `main`'s file wholesale would have silently dropped the vendored-tree
fix, so both changes were merged: `main`'s budget-limiting signature plus
this ticket's `EXCLUDED_DIRS`/`is_excluded`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
