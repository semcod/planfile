<!-- code2docs:start --># planfile

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-448-green)
> **448** functions | **62** classes | **112** files | CC̄ = 3.9

> Auto-generated project documentation from source code analysis.

**Author:** Tom Sapletta  
**License:** Apache-2.0[(LICENSE)](./LICENSE)  
**Repository:** [https://github.com/semcod/strategy](https://github.com/semcod/strategy)

## Installation

### From PyPI

```bash
pip install planfile
```

### From Source

```bash
git clone https://github.com/semcod/strategy
cd planfile
pip install -e .
```

### Optional Extras

```bash
pip install planfile[github]    # github features
pip install planfile[jira]    # jira features
pip install planfile[gitlab]    # gitlab features
pip install planfile[litellm]    # litellm features
pip install planfile[openai]    # openai features
pip install planfile[anthropic]    # anthropic features
pip install planfile[llx]    # llx features
pip install planfile[all]    # all optional features
pip install planfile[dev]    # development tools
```

## Quick Start

### CLI Usage

```bash
# Generate full documentation for your project
planfile ./my-project

# Only regenerate README
planfile ./my-project --readme-only

# Preview what would be generated (no file writes)
planfile ./my-project --dry-run

# Check documentation health
planfile check ./my-project

# Sync — regenerate only changed modules
planfile sync ./my-project
```

### Python API

```python
from planfile import generate_readme, generate_docs, Code2DocsConfig

# Quick: generate README
generate_readme("./my-project")

# Full: generate all documentation
config = Code2DocsConfig(project_name="mylib", verbose=True)
docs = generate_docs("./my-project", config=config)
```

## Generated Output

When you run `planfile`, the following files are produced:

```
<project>/
├── README.md                 # Main project README (auto-generated sections)
├── docs/
│   ├── api.md               # Consolidated API reference
│   ├── modules.md           # Module documentation with metrics
│   ├── architecture.md      # Architecture overview with diagrams
│   ├── dependency-graph.md  # Module dependency graphs
│   ├── coverage.md          # Docstring coverage report
│   ├── getting-started.md   # Getting started guide
│   ├── configuration.md    # Configuration reference
│   └── api-changelog.md    # API change tracking
├── examples/
│   ├── quickstart.py       # Basic usage examples
│   └── advanced_usage.py   # Advanced usage examples
├── CONTRIBUTING.md         # Contribution guidelines
└── mkdocs.yml             # MkDocs site configuration
```

## Configuration

Create `planfile.yaml` in your project root (or run `planfile init`):

```yaml
project:
  name: my-project
  source: ./
  output: ./docs/

readme:
  sections:
    - overview
    - install
    - quickstart
    - api
    - structure
  badges:
    - version
    - python
    - coverage
  sync_markers: true

docs:
  api_reference: true
  module_docs: true
  architecture: true
  changelog: true

examples:
  auto_generate: true
  from_entry_points: true

sync:
  strategy: markers    # markers | full | git-diff
  watch: false
  ignore:
    - "tests/"
    - "__pycache__"
```

## Sync Markers

planfile can update only specific sections of an existing README using HTML comment markers:

```markdown
<!-- planfile:start -->
# Project Title
... auto-generated content ...
<!-- planfile:end -->
```

Content outside the markers is preserved when regenerating. Enable this with `sync_markers: true` in your configuration.

## Architecture

```
planfile/
    ├── server_common├── mcp-server-example    ├── examples    ├── execution    ├── llx_validator├── planfile/    ├── models    ├── runner        ├── state    ├── sync/    ├── executor_standalone    ├── ci        ├── github        ├── jira        ├── gitlab        ├── yaml_loader    ├── loaders/        ├── cli_loader        ├── generic        ├── generator    ├── analysis/        ├── external_tools        ├── file_analyzer        ├── models    ├── core/        ├── sprint_generator        ├── redup_importer        ├── common        ├── store    ├── importers/        ├── models        ├── yaml_importer        ├── json_importer        ├── auto_loop        ├── commands        ├── extra_commands        ├── vallm_importer    ├── cli/        ├── __main__        ├── code2llm_importer        ├── base        ├── adapters        ├── prompts    ├── llm/        ├── client    ├── utils/        ├── generator        ├── project_detector        ├── priorities    ├── mcp/        ├── base    ├── integrations/        ├── metrics        ├── server        ├── config        ├── gitlab        ├── generic    ├── api/        ├── github        ├── server        ├── jira            ├── cmd_review            ├── cmd_utils            ├── cmd_compare            ├── cmd_apply            ├── cmd_sync            ├── cmd_init            ├── cmd_ticket            ├── cmd_export            ├── cmd_stats            ├── cmd_template            ├── cmd_health            ├── cmd_examples        ├── generators/            ├── cmd_validate        ├── parsers/            ├── metrics_extractor            ├── cmd_generate            ├── json_parser            ├── toon_parser        ├── 02_mcp_integration        ├── 04_llx_integration        ├── 03_proxy_routing├── cleanup_redundant├── auto_generate_planfile├── docker-entrypoint├── project    ├── run├── run_examples    ├── validate_with_llx        ├── run        ├── run        ├── run        ├── run        ├── run        ├── run        ├── run        ├── run        ├── run        ├── ci-workflow        ├── run        ├── run        ├── 01_full_workflow        ├── run        ├── run_fixed        ├── run        ├── run        ├── run_fixed        ├── run        ├── verify_planfile            ├── yaml_parser            ├── text_parser```

## API Overview

### Classes

- **`LLXValidator`** — Use LLX to validate generated code and strategies.
- **`Planfile`** — Main entry point — convenience wrapper around PlanfileStore.
- **`SyncState`** — Persist mapping between local ticket IDs and remote IDs.
- **`TaskResult`** — Result of executing a task.
- **`LLMClient`** — Simple LLM client interface.
- **`StrategyExecutor`** — Standalone strategy executor.
- **`TestResult`** — Result of running tests.
- **`BugReport`** — Generated bug report from test failures.
- **`CIRunner`** — CI/CD runner with automated bug-fix loop and ticket creation.
- **`GitHubBackend`** — GitHub Issues integration backend.
- **`JiraBackend`** — Jira integration backend.
- **`GitLabBackend`** — GitLab Issues integration backend.
- **`GenericBackend`** — Generic HTTP API backend for PM systems.
- **`PlanfileGenerator`** — Generate comprehensive planfile from file analysis.
- **`AnalysisResults`** — Results from external tool analysis.
- **`ExternalToolRunner`** — Runner for external code analysis tools.
- **`FileAnalyzer`** — Analyzes YAML/JSON files to extract issues and metrics.
- **`ExtractedIssue`** — Represents an issue extracted from a file.
- **`ExtractedMetric`** — Represents a metric extracted from a file.
- **`ExtractedTask`** — Represents a task extracted from a file.
- **`SprintGenerator`** — Generates sprints and tickets from extracted information.
- **`TicketFilter`** — Base class for ticket filters.
- **`StatusFilter`** — Filter tickets by status.
- **`PriorityFilter`** — Filter tickets by priority.
- **`SourceFilter`** — Filter tickets by source tool.
- **`LabelsFilter`** — Filter tickets by labels.
- **`TicketFilterChain`** — Chain of ticket filters.
- **`PlanfileStore`** — Read/write tickets and sprints to .planfile/ YAML files.
- **`TaskType`** — Type of task in the planfile.
- **`ModelTier`** — Model tier for different phases of work.
- **`ModelHints`** — AI model hints for different phases of task execution.
- **`Task`** — A task in a sprint - simplified and directly embedded.
- **`Sprint`** — A sprint in the planfile.
- **`QualityGate`** — Quality gate definition.
- **`Goal`** — Project goal definition.
- **`Strategy`** — Main strategy configuration - simplified and more flexible.
- **`TicketStatus`** — Status of a ticket.
- **`TicketSource`** — Who/what created the ticket.
- **`Ticket`** — Atomic unit of work in planfile.
- **`VallmParser`** — Parser for vallm validation.toon files.
- **`EvolutionParser`** — State machine parser for evolution.toon NEXT[] sections.
- **`TicketRef`** — Reference to a created/updated ticket.
- **`TicketStatus`** — Status of a ticket.
- **`PMBackend`** — Protocol for PM system backends.
- **`BasePMBackend`** — Base class for PM backends with common functionality.
- **`LLMTestResult`** — —
- **`BaseLLMAdapter`** — —
- **`LiteLLMAdapter`** — —
- **`OpenRouterAdapter`** — —
- **`LocalLLMAdapter`** — —
- **`LLMTestRunner`** — —
- **`DetectedProject`** — Container for detected project information.
- **`IntegrationConfig`** — Manages integration configuration with support for multiple config files.
- **`TicketCreate`** — —
- **`TicketUpdate`** — —
- **`ProjectMetrics`** — Project metrics from LLX analysis.
- **`LLXIntegration`** — Integration with LLX for code analysis and model selection.
- **`ProxyClient`** — Client for interacting with Proxym API.
- **`UserType`** — —
- **`User`** — —
- **`UserService`** — —
- **`UserController`** — —

### Functions

- `get_planfile(start_path)` — Return a cached Planfile instance discovered from the project tree.
- `planfile_generate(arguments)` — —
- `planfile_apply(arguments)` — —
- `planfile_review(arguments)` — —
- `main()` — —
- `example_create_strategy()` — Create a strategy using LLX with local LLM.
- `example_validate_strategy()` — Load and validate an existing strategy.
- `example_run_strategy()` — Run strategy to create tickets (dry run).
- `example_verify_strategy()` — Verify strategy execution.
- `example_programmatic_strategy()` — Create strategy programmatically without LLM.
- `create_validation_script()` — Create a validation script that uses LLX.
- `quick_ticket(title, tool)` — One-liner ticket creation for tools.
- `load_valid_strategy(path)` — Load and validate strategy from YAML file.
- `verify_strategy_post_execution(strategy, project_path, backend)` — Verify strategy after execution.
- `analyze_project_metrics(project_path)` — Analyze project metrics using available tools.
- `apply_strategy_to_tickets(strategy, project_path, backend, dry_run)` — Apply strategy to create tickets in PM system.
- `review_strategy(strategy, project_path, backends, backend_name)` — Review strategy execution by checking ticket statuses.
- `run_strategy(strategy_path, project_path, backend, dry_run)` — Run strategy: load, validate, and apply.
- `create_openai_client(api_key, model)` — Create an OpenAI client.
- `create_litellm_client(api_key, model)` — Create a LiteLLM client.
- `execute_strategy(strategy_path, project_path)` — Execute strategy from file - convenience function.
- `load_yaml(file_path)` — Load YAML file and return as dictionary.
- `save_yaml(data, file_path)` — Save dictionary to YAML file.
- `load_strategy_yaml(file_path)` — Load strategy from YAML file.
- `save_strategy_yaml(strategy, file_path)` — Save strategy to YAML file.
- `load_tasks_yaml(file_path)` — Load task patterns from YAML file.
- `merge_strategy_with_tasks(strategy, tasks_file)` — Merge additional task patterns into a planfile.
- `validate_strategy_schema(file_path)` — Validate strategy YAML file and return list of issues.
- `load_from_json(file_path)` — Load JSON file and return as dictionary.
- `save_to_json(data, file_path)` — Save dictionary to JSON file.
- `load_strategy_from_json(file_path)` — Load strategy from JSON file.
- `save_strategy_to_json(strategy, file_path)` — Save strategy to JSON file.
- `export_results_to_markdown(results, file_path)` — Export strategy results to Markdown file.
- `run_external_analysis(project_path)` — Convenience function to run all external tools.
- `import_redup(file_path)` — Import duplication issues from redup toon.yaml file.
- `normalize_ticket_dict(item)` — Ensure minimal ticket fields exist.
- `load_structured_tickets(path, loader)` — Load tickets from JSON/YAML-like structured data.
- `register_importer(name, importer_cls)` — —
- `import_from_source(path, source)` — Auto-detect format and import tickets.
- `import_yaml(path)` — Parse a YAML file containing ticket data.
- `import_json(path)` — Parse a JSON file containing ticket data.
- `get_backend(backend_type)` — Get backend instance by type.
- `auto_loop(strategy, project_path, backend, max_iterations)` — Run automated CI/CD loop: test → ticket → fix → retest.
- `ci_status(project_path)` — Check current CI status without running tests.
- `version_callback(value)` — —
- `main_callback(version)` — —
- `main()` — Main CLI entry point.
- `add_extra_commands(app)` — Add health, examples, and sync command groups to the CLI app.
- `import_vallm(toon_path, auto_priority)` — Parse vallm validation.toon ERRORS[] → ticket dicts.
- `import_code2llm(toon_path, auto_priority, sprint)` — Parse evolution.toon NEXT[] → ticket dicts.
- `build_strategy_prompt(metrics, sprints, focus)` — Build a structured prompt for strategy generation.
- `call_llm(prompt, model, temperature)` — Call LLM via LiteLLM. Falls back to llx proxy if available.
- `generate_strategy(project_path)` — Generate a complete strategy from project analysis.
- `detect_project(project_path)` — Auto-detect project information from various sources.
- `get_detected_values()` — Get detected project values as a dictionary for use in CLI.
- `calculate_task_priority(base_priority, task_type, sprint_id, weight_factors)` — Calculate task priority based on type, sprint, and base priority.
- `map_priority_to_system(priority, system)` — Map generic priority to system-specific priority.
- `get_priority_color(priority)` — Get color code for priority (for UI display).
- `analyze_project_metrics(project_path)` — Analyze project metrics for strategy review.
- `calculate_strategy_health(strategy_results)` — Calculate health metrics for a strategy execution.
- `handle_tool_call(name, arguments)` — Dispatch an MCP tool call and return the result dict.
- `main()` — Run a minimal MCP stdio server.
- `list_tickets(sprint, status)` — —
- `create_ticket(body)` — —
- `get_ticket(ticket_id)` — —
- `update_ticket(ticket_id, body)` — —
- `delete_ticket(ticket_id)` — —
- `move_ticket(ticket_id, to_sprint)` — —
- `health()` — —
- `review_strategy_cli(strategy_path, project_path, backend, config_file)` — Review strategy execution and progress.
- `get_backend(backend_type, config)` — Get backend instance by type and config.
- `compare_strategies(s1, s2)` — Compare two strategies and return differences.
- `register_compare_commands(app)` — Register compare command on the typer app.
- `apply_strategy_cli(strategy_path, project_path, backend, config_file)` — Apply a strategy to create tickets.
- `create_sync_app()` — Create the sync command app.
- `github(directory, dry_run, direction)` — Sync tickets with GitHub Issues.
- `gitlab(directory, dry_run, direction)` — Sync tickets with GitLab Issues.
- `jira(directory, dry_run, direction)` — Sync tickets with Jira.
- `all(directory, dry_run, direction)` — Sync tickets with all configured integrations.
- `sync_integration(integration_name, directory, dry_run, direction)` — Sync with a specific integration.
- `sync_to_external(backend, tickets, dry_run)` — Sync planfile tickets to external system.
- `sync_from_external(backend, store, dry_run)` — Sync tickets from external system to planfile.
- `find_planfile_ticket(external_ticket, store)` — Find corresponding planfile ticket for external ticket.
- `init_strategy_cli(output, yes)` — Interactive wizard — tworzy strategię przez zadawanie pytań.
- `register_ticket_commands(app)` — Register ticket subcommands on the typer app.
- `export_to_csv(strategy, file_path)` — Export strategy to CSV format.
- `export_to_html(strategy, file_path)` — Export strategy to HTML format.
- `register_export_commands(app)` — Register export and merge commands on the typer app.
- `calculate_strategy_stats(strategy)` — Calculate statistics for a strategy.
- `register_stats_commands(app)` — Register stats command on the typer app.
- `generate_template(project_type, domain)` — Generate a strategy template based on project type and domain.
- `register_template_commands(app)` — Register template command on the typer app.
- `create_health_app()` — Create and return the health sub-app.
- `create_examples_app()` — Create and return the examples sub-app.
- `validate_strategy_cli(strategy_path, verbose)` — Validate a strategy YAML file.
- `extract_key_metrics(analysis_result, external_metrics)` — Extract key metrics from analysis.
- `generate_strategy_cli(project_path, output, model, sprints)` — Generate strategy.yaml from project analysis + LLM.
- `generate_from_files_cmd(project_path, output, project_name, max_sprints)` — Generate planfile from file analysis (no LLM required).
- `analyze_json(file_path)` — Analyze JSON file.
- `analyze_toon(file_path)` — Analyze Toon format files with enhanced parsing.
- `run_mcp_tool(tool_name, arguments)` — Simulate running an MCP tool.
- `simulate_planfile_generate(args)` — Simulate planfile generate tool.
- `simulate_planfile_apply(args)` — Simulate planfile apply tool.
- `simulate_planfile_review(args)` — Simulate planfile review tool.
- `example_mcp_session()` — Example of an LLM agent using planfile MCP tools.
- `create_mcp_tool_definitions()` — Create MCP tool definitions for integration.
- `example_metric_driven_planning()` — Example: Generate strategy based on actual project metrics.
- `create_llx_config_example()` — Create example LLX configuration for planfile integration.
- `example_strategy_generation_with_proxy()` — Example: Generate strategy using proxy for smart model routing.
- `create_proxy_config_example()` — Create example proxy configuration for planfile integration.
- `example_budget_tracking()` — Example: Budget tracking with proxy.
- `check_env()` — —
- `validate_config()` — —
- `setup_workspace()` — —
- `run_command()` — —
- `main()` — —
- `print_header()` — —
- `print_step()` — —
- `print_success()` — —
- `print_error()` — —
- `print_info()` — —
- `run_example()` — —
- `check_prerequisites()` — —
- `setup_environment()` — —
- `run_all_examples()` — —
- `run_specific_example()` — —
- `show_usage()` — —
- `list_examples()` — —
- `main()` — —
- `validate_file()` — —
- `print()` — —
- `print()` — —
- `print()` — —
- `print()` — —
- `create_user()` — —
- `get_user()` — —
- `update_user()` — —
- `setattr()` — —
- `delete_user()` — —
- `get_users_by_type()` — —
- `authenticate()` — —
- `export_to_json()` — —
- `import_from_json()` — —
- `get_statistics()` — —
- `validate_planfile()` — —
- `print()` — —
- `extract_from_yaml_structure(data, path, parent_key)` — Extract issues from YAML structure.
- `analyze_yaml(file_path)` — Analyze YAML file with better error handling.
- `analyze_text(file_path)` — Analyze text content for TODOs, FIXMEs, and metrics.


## Project Structure

📄 `auto_generate_planfile`
📄 `cleanup_redundant`
📄 `docker-entrypoint` (5 functions)
📄 `examples.advanced-usage.ci-workflow`
📄 `examples.advanced-usage.run`
📄 `examples.bash-generation.verify_planfile` (4 functions)
📄 `examples.cli-commands.run`
📄 `examples.cli-commands.run_fixed`
📄 `examples.code2llm.run`
📄 `examples.comprehensive-example.run`
📄 `examples.demo-without-keys.run`
📄 `examples.ecosystem.01_full_workflow` (17 functions, 6 classes)
📄 `examples.ecosystem.02_mcp_integration` (6 functions)
📄 `examples.ecosystem.03_proxy_routing` (7 functions, 1 classes)
📄 `examples.ecosystem.04_llx_integration` (9 functions, 2 classes)
📄 `examples.external-tools.run`
📄 `examples.github.run` (6 functions)
📄 `examples.gitlab.run` (7 functions)
📄 `examples.integrated-functionality.run`
📄 `examples.jira.run` (9 functions)
📄 `examples.llm-integration.run`
📄 `examples.llx_validator` (7 functions, 1 classes)
📄 `examples.multi-ticket.run` (8 functions)
📄 `examples.quick-start.run`
📄 `examples.quick-start.run_fixed`
📄 `examples.redup.run`
📄 `examples.run`
📄 `examples.validate_with_llx` (1 functions)
📄 `examples.vallm.run`
📄 `mcp-server-example` (4 functions)
📦 `planfile` (8 functions, 1 classes)
📦 `planfile.analysis`
📄 `planfile.analysis.external_tools` (13 functions, 2 classes)
📄 `planfile.analysis.file_analyzer` (10 functions, 1 classes)
📄 `planfile.analysis.generator` (17 functions, 1 classes)
📦 `planfile.analysis.generators`
📄 `planfile.analysis.generators.metrics_extractor` (6 functions)
📄 `planfile.analysis.models` (2 functions, 3 classes)
📦 `planfile.analysis.parsers`
📄 `planfile.analysis.parsers.json_parser` (1 functions)
📄 `planfile.analysis.parsers.text_parser` (1 functions)
📄 `planfile.analysis.parsers.toon_parser` (7 functions)
📄 `planfile.analysis.parsers.yaml_parser` (2 functions)
📄 `planfile.analysis.sprint_generator` (10 functions, 1 classes)
📦 `planfile.api`
📄 `planfile.api.server` (7 functions, 2 classes)
📄 `planfile.ci` (9 functions, 3 classes)
📦 `planfile.cli`
📄 `planfile.cli.__main__`
📄 `planfile.cli.auto_loop` (9 functions)
📄 `planfile.cli.cmd.cmd_apply` (4 functions)
📄 `planfile.cli.cmd.cmd_compare` (2 functions)
📄 `planfile.cli.cmd.cmd_examples` (3 functions)
📄 `planfile.cli.cmd.cmd_export` (3 functions)
📄 `planfile.cli.cmd.cmd_generate` (2 functions)
📄 `planfile.cli.cmd.cmd_health` (1 functions)
📄 `planfile.cli.cmd.cmd_init` (4 functions)
📄 `planfile.cli.cmd.cmd_review` (1 functions)
📄 `planfile.cli.cmd.cmd_stats` (2 functions)
📄 `planfile.cli.cmd.cmd_sync` (9 functions)
📄 `planfile.cli.cmd.cmd_template` (2 functions)
📄 `planfile.cli.cmd.cmd_ticket` (2 functions)
📄 `planfile.cli.cmd.cmd_utils` (5 functions)
📄 `planfile.cli.cmd.cmd_validate` (1 functions)
📄 `planfile.cli.commands` (3 functions)
📄 `planfile.cli.extra_commands` (1 functions)
📄 `planfile.cli.project_detector` (10 functions, 1 classes)
📦 `planfile.core`
📄 `planfile.core.models` (17 functions, 11 classes)
📄 `planfile.core.store` (27 functions, 7 classes)
📄 `planfile.examples` (5 functions)
📄 `planfile.execution`
📄 `planfile.executor_standalone` (12 functions, 3 classes)
📦 `planfile.importers` (2 functions)
📄 `planfile.importers.code2llm_importer` (9 functions, 1 classes)
📄 `planfile.importers.common` (2 functions)
📄 `planfile.importers.json_importer` (1 functions)
📄 `planfile.importers.redup_importer` (5 functions)
📄 `planfile.importers.vallm_importer` (10 functions, 1 classes)
📄 `planfile.importers.yaml_importer` (1 functions)
📦 `planfile.integrations`
📄 `planfile.integrations.base`
📄 `planfile.integrations.config` (11 functions, 1 classes)
📄 `planfile.integrations.generic`
📄 `planfile.integrations.github`
📄 `planfile.integrations.gitlab`
📄 `planfile.integrations.jira`
📦 `planfile.llm`
📄 `planfile.llm.adapters` (5 functions, 6 classes)
📄 `planfile.llm.client` (1 functions)
📄 `planfile.llm.generator` (6 functions)
📄 `planfile.llm.prompts` (1 functions)
📦 `planfile.loaders`
📄 `planfile.loaders.cli_loader` (10 functions)
📄 `planfile.loaders.yaml_loader` (15 functions)
📦 `planfile.mcp`
📄 `planfile.mcp.server` (4 functions)
📄 `planfile.models`
📄 `planfile.runner` (6 functions)
📄 `planfile.server_common` (1 functions)
📦 `planfile.sync`
📄 `planfile.sync.base` (21 functions, 4 classes)
📄 `planfile.sync.generic` (10 functions, 1 classes)
📄 `planfile.sync.github` (8 functions, 1 classes)
📄 `planfile.sync.gitlab` (8 functions, 1 classes)
📄 `planfile.sync.jira` (10 functions, 1 classes)
📄 `planfile.sync.state` (5 functions, 1 classes)
📦 `planfile.utils`
📄 `planfile.utils.metrics` (5 functions)
📄 `planfile.utils.priorities` (3 functions)
📄 `project`
📄 `run_examples` (13 functions)

## Requirements

- Python >= >=3.10
- typer >=0.12- rich >=13.0- pydantic >=2.0- pydantic-settings >=2.0- pyyaml >=6.0- requests >=2.31- httpx >=0.27- filelock >=3.0- python-dotenv >=1.0- PyGithub >=2.0

## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>
- Tom Sapletta <tom-sapletta-com@users.noreply.github.com>

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/semcod/strategy
cd planfile

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

- 📖 [Full Documentation](https://github.com/semcod/strategy/tree/main/docs) — API reference, module docs, architecture
- 🚀 [Getting Started](https://github.com/semcod/strategy/blob/main/docs/getting-started.md) — Quick start guide
- 📚 [API Reference](https://github.com/semcod/strategy/blob/main/docs/api.md) — Complete API documentation
- 🔧 [Configuration](https://github.com/semcod/strategy/blob/main/docs/configuration.md) — Configuration options
- 💡 [Examples](./examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `docs/api.md` | Consolidated API reference | [View](./docs/api.md) |
| `docs/modules.md` | Module reference with metrics | [View](./docs/modules.md) |
| `docs/architecture.md` | Architecture with diagrams | [View](./docs/architecture.md) |
| `docs/dependency-graph.md` | Dependency graphs | [View](./docs/dependency-graph.md) |
| `docs/coverage.md` | Docstring coverage report | [View](./docs/coverage.md) |
| `docs/getting-started.md` | Getting started guide | [View](./docs/getting-started.md) |
| `docs/configuration.md` | Configuration reference | [View](./docs/configuration.md) |
| `docs/api-changelog.md` | API change tracking | [View](./docs/api-changelog.md) |
| `CONTRIBUTING.md` | Contribution guidelines | [View](./CONTRIBUTING.md) |
| `examples/` | Usage examples | [Browse](./examples) |
| `mkdocs.yml` | MkDocs configuration | — |

<!-- code2docs:end -->