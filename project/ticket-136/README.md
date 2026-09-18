# Ticket 136: integrate NL-DSL-LLM pattern with multilingual parser and CLI MCP tools

- **ID**: ticket-136
- **Owner**: human:tom
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-09-18
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION

## Goal and scope

Adopt the `wellmanifest/nl-dsl-llm` standard in planfile:
1. Multilingual NL fast-path parser (PL + EN) for tickets, sprints, strategies, and config.
2. Adaptive LLM fallback translation for complex/unrecognized queries.
3. CLI commands `planfile ask <query>` and `planfile mcp` server command.
4. MCP tools parity (`planfile_ask`, `planfile_describe_grammar`).
5. REST API parity (`POST /query` alongside `POST /dsl`).

## Acceptance criteria

- [x] AC-01: Multilingual NL parsing support (PL + EN) for ticket list/create/show/done/delete commands.
- [x] AC-02: `planfile ask <query>` CLI command supports natural language execution with output formatting.
- [x] AC-03: `planfile mcp` CLI command launches the stdio MCP server.
- [x] AC-04: MCP server tools `planfile_ask` and `planfile_describe_grammar` are implemented and guarded.
- [x] AC-05: Test suite in `tests/test_nl_dsl_llm.py` verifies NL parsing, CLI commands, and MCP tools.
- [x] AC-06: Governance checks pass (`./project/governance-check.sh`).

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
