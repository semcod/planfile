# CLI DSL Usage Examples

This directory contains examples for using planfile DSL via the command-line interface.

## Overview

The `planfile dsl` command allows you to execute natural language-like commands against planfile. You can run single commands or start an interactive REPL shell.

## Running DSL Commands

### Single Command

```bash
planfile dsl "list tickets sprint=current"
```

### Interactive Shell

```bash
planfile dsl
```

Then type commands:
```
planfile> list tickets sprint=current
planfile> create ticket "Fix bug" priority=high
planfile> done ticket PLF-001
planfile> exit
```

## Format Options

```bash
planfile dsl "list tickets" --format json
planfile dsl "list tickets" --format yaml
planfile dsl "list tickets" --format text  # default
```

## Project Path

```bash
planfile dsl "list tickets" --project /path/to/project
```

## Fail on Error

```bash
planfile dsl "update ticket PLF-999 status=done" --fail-on-error
```

## Examples

- `01_dsl_usage.py` — Comprehensive list of DSL command examples

## Common Commands

### Ticket Operations

```bash
# List tickets
planfile dsl "list tickets sprint=current"

# Create ticket
planfile dsl 'create ticket "Fix login bug" priority=high sprint=1 labels=backend,auth'

# Show ticket
planfile dsl "show ticket PLF-001"

# Update ticket
planfile dsl "update ticket PLF-001 status=done"

# Move ticket
planfile dsl "move ticket PLF-001 to sprint=2"

# Mark as done
planfile dsl "done ticket PLF-001"

# Start ticket
planfile dsl "start ticket PLF-001"

# Block ticket
planfile dsl 'block ticket PLF-001 reason="Waiting for API"'

# Delete ticket
planfile dsl "delete ticket PLF-001"
```

### Sprint Operations

```bash
# List sprints
planfile dsl "list sprints"

# Add sprint
planfile dsl 'add sprint "Sprint 4" days=14'
```

### Validation & Sync

```bash
# Validate tickets
planfile dsl "validate"

# Sync to GitHub
planfile dsl "sync github"

# Sync all integrations
planfile dsl "sync all"
```

### Query & Export

```bash
# Query with filters
planfile dsl "query tickets where priority=high status=open"

# Export to YAML
planfile dsl "export format=yaml"

# Export to JSON
planfile dsl "export format=json"
```

## Help

```bash
planfile dsl "help"
```
