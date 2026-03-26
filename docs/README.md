<!-- code2docs:start --># planfile

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-143-green)
> **143** functions | **27** classes | **34** files | CC̄ = 4.8

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
├── planfile/        ├── llx_validator        ├── summary    ├── runner        ├── yaml_loader    ├── loaders/        ├── cli_loader        ├── auto_loop    ├── cli/        ├── __main__        ├── generator        ├── commands    ├── llm/        ├── prompts        ├── client    ├── utils/        ├── priorities        ├── metrics    ├── integrations/        ├── gitlab        ├── jira        ├── github        ├── generic            ├── 02_mcp_integration    ├── ci_runner            ├── 03_proxy_routing├── docker-entrypoint├── project        ├── validate_with_llx            ├── 01_full_workflow            ├── verify_planfile            ├── 04_llx_integration    ├── models        ├── base```

## API Overview

### Classes

- **`LLXValidator`** — Use LLX to validate generated code and strategies.
- **`StrategyRunner`** — Main runner for applying and reviewing strategies.
- **`GitLabBackend`** — GitLab Issues integration backend.
- **`JiraBackend`** — Jira integration backend.
- **`GitHubBackend`** — GitHub Issues integration backend.
- **`GenericBackend`** — Generic HTTP API backend for PM systems.
- **`TestResult`** — Result of running tests.
- **`BugReport`** — Generated bug report from test failures.
- **`CIRunner`** — CI/CD runner with automated bug-fix loop.
- **`ProxyClient`** — Client for interacting with Proxym API.
- **`UserType`** — —
- **`User`** — —
- **`UserService`** — —
- **`UserController`** — —
- **`ProjectMetrics`** — Project metrics from LLX analysis.
- **`LLXIntegration`** — Integration with LLX for code analysis and model selection.
- **`TaskType`** — Type of task in the planfile.
- **`ModelTier`** — Model tier for different phases of work.
- **`ModelHints`** — AI model hints for different phases of task execution.
- **`TaskPattern`** — A pattern for generating tasks.
- **`Sprint`** — A sprint in the planfile.
- **`QualityGate`** — Quality gate definition.
- **`Strategy`** — Main strategy configuration.
- **`TicketRef`** — Reference to a created/updated ticket.
- **`TicketStatus`** — Status of a ticket.
- **`PMBackend`** — Protocol for PM system backends.
- **`BasePMBackend`** — Base class for PM backends with common functionality.

### Functions

- `create_validation_script()` — Create a validation script that uses LLX.
- `create_summary()` — Create a summary of all changes made.
- `apply_strategy(strategy, project_path, backends, backend_name)` — Apply a strategy to create/update tickets.
- `review_strategy(strategy, project_path, backends, backend_name)` — Review strategy execution by checking ticket statuses.
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
- `get_backend(backend_type)` — Get backend instance by type.
- `auto_loop(strategy, project_path, backend, max_iterations)` — Run automated CI/CD loop: test → ticket → fix → retest.
- `ci_status(project_path)` — Check current CI status without running tests.
- `generate_strategy(project_path)` — Generate a complete strategy from project analysis.
- `get_backend(backend_type, config)` — Get backend instance by type and config.
- `apply_strategy_cli(strategy_path, project_path, backend, config_file)` — Apply a strategy to create tickets.
- `review_strategy_cli(strategy_path, project_path, backend, config_file)` — Review strategy execution and progress.
- `validate_strategy_cli(strategy_path, verbose)` — Validate a strategy YAML file.
- `generate_strategy_cli(project_path, output, model, sprints)` — Generate strategy.yaml from project analysis + LLM.
- `main()` — Main CLI entry point.
- `build_strategy_prompt(metrics, sprints, focus)` — Build a structured prompt for strategy generation.
- `call_llm(prompt, model, temperature)` — Call LLM via LiteLLM. Falls back to llx proxy if available.
- `calculate_task_priority(base_priority, task_type, sprint_id, weight_factors)` — Calculate task priority based on type, sprint, and base priority.
- `map_priority_to_system(priority, system)` — Map generic priority to system-specific priority.
- `get_priority_color(priority)` — Get color code for priority (for UI display).
- `analyze_project_metrics(project_path)` — Analyze project metrics for strategy review.
- `calculate_strategy_health(strategy_results)` — Calculate health metrics for a strategy execution.
- `run_mcp_tool(tool_name, arguments)` — Simulate running an MCP tool.
- `simulate_planfile_generate(args)` — Simulate planfile generate tool.
- `simulate_planfile_apply(args)` — Simulate planfile apply tool.
- `simulate_planfile_review(args)` — Simulate planfile review tool.
- `example_mcp_session()` — Example of an LLM agent using planfile MCP tools.
- `create_mcp_tool_definitions()` — Create MCP tool definitions for integration.
- `main()` — CLI entry point.
- `example_strategy_generation_with_proxy()` — Example: Generate strategy using proxy for smart model routing.
- `create_proxy_config_example()` — Create example proxy configuration for planfile integration.
- `example_budget_tracking()` — Example: Budget tracking with proxy.
- `check_env()` — —
- `validate_config()` — —
- `setup_workspace()` — —
- `run_command()` — —
- `main()` — —
- `validate_file()` — —
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
- `example_metric_driven_planning()` — Example: Generate strategy based on actual project metrics.
- `create_llx_config_example()` — Create example LLX configuration for planfile integration.


## Project Structure

📄 `docker-entrypoint` (5 functions)
📦 `planfile`
📄 `planfile.ci_runner` (10 functions, 3 classes)
📦 `planfile.cli`
📄 `planfile.cli.__main__`
📄 `planfile.cli.auto_loop` (3 functions)
📄 `planfile.cli.commands` (6 functions)
📄 `planfile.examples.bash-generation.verify_planfile` (4 functions)
📄 `planfile.examples.ecosystem.01_full_workflow` (17 functions, 6 classes)
📄 `planfile.examples.ecosystem.02_mcp_integration` (6 functions)
📄 `planfile.examples.ecosystem.03_proxy_routing` (7 functions, 1 classes)
📄 `planfile.examples.ecosystem.04_llx_integration` (9 functions, 2 classes)
📄 `planfile.examples.llx_validator` (7 functions, 1 classes)
📄 `planfile.examples.summary` (1 functions)
📄 `planfile.examples.validate_with_llx` (1 functions)
📦 `planfile.integrations`
📄 `planfile.integrations.base` (9 functions, 4 classes)
📄 `planfile.integrations.generic` (8 functions, 1 classes)
📄 `planfile.integrations.github` (7 functions, 1 classes)
📄 `planfile.integrations.gitlab` (7 functions, 1 classes)
📄 `planfile.integrations.jira` (9 functions, 1 classes)
📦 `planfile.llm`
📄 `planfile.llm.client` (1 functions)
📄 `planfile.llm.generator` (5 functions)
📄 `planfile.llm.prompts` (1 functions)
📦 `planfile.loaders`
📄 `planfile.loaders.cli_loader` (5 functions)
📄 `planfile.loaders.yaml_loader` (7 functions)
📄 `planfile.models` (2 functions, 7 classes)
📄 `planfile.runner` (8 functions, 1 classes)
📦 `planfile.utils`
📄 `planfile.utils.metrics` (2 functions)
📄 `planfile.utils.priorities` (3 functions)
📄 `project`

## Requirements

- Python >= >=3.10
- typer >=0.12- rich >=13.0- pydantic >=2.0- pydantic-settings >=2.0- pyyaml >=6.0- requests >=2.31- httpx >=0.27

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