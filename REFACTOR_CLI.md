# CLI Refactoring Plan — Planfile

## Current State Analysis

### Fan-out Problem (33 dependencies)
Current `planfile/cli/commands.py` imports from 15+ modules:
- `planfile.cli.auto_loop` → CIRunner, GitHub/GitLab/Jira backends
- `planfile.cli.cmd.cmd_apply` → apply_strategy_cli
- `planfile.cli.cmd.cmd_generate` → generate_strategy_cli, generate_from_files_cmd
- `planfile.cli.cmd.cmd_init` → init_strategy_cli
- `planfile.cli.cmd.cmd_review` → review_strategy_cli
- `planfile.cli.cmd.cmd_validate` → validate_strategy_cli
- `planfile.cli.cmd.cmd_compare` → register_compare_commands
- `planfile.cli.cmd.cmd_export` → register_export_commands
- `planfile.cli.cmd.cmd_stats` → register_stats_commands
- `planfile.cli.cmd.cmd_template` → register_template_commands
- `planfile.cli.cmd.cmd_ticket` → register_ticket_commands
- `planfile.cli.extra_commands` → add_extra_commands (health, examples)
- Plus indirect imports from each cmd module

## Proposed Restructure

### New Module Hierarchy

```
planfile/cli/
├── __init__.py              # Minimal, exports main app only
├── __main__.py              # Entry point
├── core/                    # NEW: Shared CLI infrastructure
│   ├── __init__.py
│   ├── console.py           # Rich console singleton
│   ├── errors.py            # Common error handling (typer.Exit patterns)
│   ├── progress.py          # Progress bar helpers
│   └── registry.py          # Command registry (replaces scattered imports)
├── groups/                  # NEW: Command groups (replace cmd/)
│   ├── __init__.py
│   ├── generate/            # Was: cmd_generate, cmd_template
│   │   ├── __init__.py      # Exports: generate, template commands
│   │   ├── strategy.py      # generate_strategy_cli
│   │   ├── files.py         # generate_from_files_cmd
│   │   └── template.py      # register_template_commands
│   ├── init/                # Was: cmd_init
│   │   ├── __init__.py
│   │   ├── strategy.py      # init_strategy_cli
│   │   └── detector.py      # Project detection logic
│   ├── review/              # Was: cmd_review, cmd_validate, cmd_apply
│   │   ├── __init__.py
│   │   ├── review.py        # review_strategy_cli
│   │   ├── validate.py      # validate_strategy_cli
│   │   └── apply.py         # apply_strategy_cli
│   ├── sync/                # Was: cmd_sync
│   │   ├── __init__.py
│   │   ├── main.py          # sync_integration + helpers
│   │   ├── github.py        # github command
│   │   ├── gitlab.py        # gitlab command
│   │   ├── jira.py          # jira command
│   │   ├── markdown.py      # markdown command
│   │   └── all.py           # all command
│   ├── ticket/              # Was: cmd_ticket
│   │   ├── __init__.py
│   │   ├── commands.py      # register_ticket_commands
│   │   ├── create.py        # Ticket creation logic
│   │   ├── list.py          # Ticket listing
│   │   └── update.py        # Ticket updates
│   ├── query/               # Was: cmd_stats, cmd_compare, cmd_export
│   │   ├── __init__.py
│   │   ├── stats.py         # register_stats_commands
│   │   ├── compare.py       # register_compare_commands
│   │   └── export.py        # register_export_commands
│   └── auto/                # Was: auto_loop.py
│       ├── __init__.py
│       ├── loop.py          # Auto-loop logic
│       ├── ci.py            # CIRunner
│       └── backends.py      # GitHub/GitLab/Jira backend factory
└── commands.py              # SHRINK: Only orchestrates group registration
```

## Migration Strategy

### Phase 1: Extract Shared Infrastructure
1. Create `planfile/cli/core/console.py`
   - Move `console = Console()` from scattered locations
   - Centralize Rich console configuration

2. Create `planfile/cli/core/errors.py`
   - Standardize `typer.Exit(1)` patterns
   - Add helper: `exit_with_error(message: str)`

3. Create `planfile/cli/core/progress.py`
   - Extract Progress spinner patterns
   - Reusable `with_spinner(description, fn)` context

### Phase 2: Group Commands by Domain
Each group/ directory becomes a self-contained package:

**Example: sync/ migration**
```python
# planfile/cli/groups/sync/__init__.py
from .github import github_cmd
from .gitlab import gitlab_cmd
from .jira import jira_cmd
from .markdown import markdown_cmd
from .all import all_cmd

def register_sync_commands(app: typer.Typer) -> None:
    sync_app = typer.Typer(help="Sync tickets with external systems")
    sync_app.command()(github_cmd)
    sync_app.command()(gitlab_cmd)
    sync_app.command()(jira_cmd)
    sync_app.command()(markdown_cmd)
    sync_app.command("all")(all_cmd)
    app.add_typer(sync_app, name="sync")
```

### Phase 3: Reduce commands.py Fan-out
Target `planfile/cli/commands.py`:
```python
import typer
from planfile.cli.core.console import console
from planfile.cli.groups import (
    register_generate_commands,
    register_init_commands,
    register_review_commands,
    register_sync_commands,
    register_ticket_commands,
    register_query_commands,
    register_auto_commands,
)

app = typer.Typer(help="planfile — universal ticket standard")

# Register all command groups
register_generate_commands(app)
register_init_commands(app)
register_review_commands(app)
register_sync_commands(app)
register_ticket_commands(app)
register_query_commands(app)
register_auto_commands(app)
```
**Fan-out reduced: 15 → 7**

## Benefits

1. **Reduced Fan-out**: From 33 to ~12 in main CLI module
2. **Better Cohesion**: Related commands grouped together
3. **Easier Testing**: Each group can be tested independently
4. **Clearer Ownership**: Each directory has a single responsibility
5. **Simpler Refactoring**: Changes isolated to specific domains

## Migration Checklist

- [ ] Create `cli/core/` with console, errors, progress
- [ ] Move `auto_loop.py` → `groups/auto/`
- [ ] Split `cmd_sync.py` → `groups/sync/`
- [ ] Split `cmd_generate.py` + `cmd_template.py` → `groups/generate/`
- [ ] Split `cmd_review.py` + `cmd_validate.py` + `cmd_apply.py` → `groups/review/`
- [ ] Split `cmd_ticket.py` → `groups/ticket/`
- [ ] Merge `cmd_stats.py` + `cmd_compare.py` + `cmd_export.py` → `groups/query/`
- [ ] Update `commands.py` to use new group imports
- [ ] Delete `cmd/` directory after migration
- [ ] Update tests to use new module paths
