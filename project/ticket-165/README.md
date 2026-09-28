# Ticket 165: integrate native rust acceleration crates into planfile

- **ID**: ticket-165
- **Owner**: agent:gemini
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION — user requests acceleration and native planfile-* integration; 2026-09-28.

## Goal and scope

Integrate the extracted native Rust crates (`planfile-io`, `planfile-semantic`, `planfile-analyzer`, `planfile-graph`, `planfile-dsl`, `planfile-journal`) into the core `planfile` modules with graceful pure-Python fallback.

## Acceptance criteria

- [x] AC-01: When `planfile_io` is importable, `read_yaml_fast` delegates to native parser.
- [x] AC-02: When `planfile_semantic` is importable, `lexical_similarity` and `similarity_matrix` delegate to Rust.
- [x] AC-03: When `planfile_analyzer` is importable, native analysis is used in file analysis.
- [x] AC-04: When `planfile_graph` is importable, `build_tree` and `tree_progress` delegate to native DAG engine.
- [x] AC-05: When `planfile_dsl` is importable, `DSLParser.parse` delegates to fast bilingual lexer.
- [x] AC-06: When `planfile_journal` is importable, `read_jsonl_tail` delegates to native memory-mapped reverse tail.
- [x] AC-07: Graceful pure-Python fallback remains fully functional for every module.
- [x] AC-08: Full test suite and governance checks pass.
- [x] AC-09: `Planfile.execution_waves()` partitions sprint tickets into parallel layers.
- [x] AC-10: `Planfile.next_tickets()` supports batch dispatch with critical path priority and disjoint file locking.

## Tracking boundary

This directory contains the minimal reviewed intent and acceptance criteria.
