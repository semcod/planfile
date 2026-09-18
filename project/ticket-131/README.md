# Ticket 131: Add planfile shell and sh interactive commands

- **ID**: ticket-131
- **Owner**: tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-18
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION (user requested planfile sh/shell in chat)

## Goal and scope

Add `planfile shell` and `planfile sh` top-level CLI commands to launch the interactive planfile DSL shell (REPL), and allow `planfile dsl` without subcommands to launch the interactive shell directly.

## Acceptance criteria

- [x] AC-01: `planfile shell` and `planfile sh` are available as top-level CLI commands.
- [x] AC-02: `planfile dsl` invoked without subcommand drops into the interactive DSL shell.
- [x] AC-03: `planfile shell --help` and `planfile sh --help` display help and options.
- [x] AC-04: CLI tests verify `shell`, `sh`, and `dsl` help and command invocations.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
