# Strategy

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/strategy.svg)](https://pypi.org/project/strategy/)

**Strategy** is a strategic PM layer for managing sprints and strategies across external ticket systems. It provides a unified interface to create and manage tickets in Jira, GitHub, GitLab, and other PM systems.

## Features

- 🎯 **Strategy Modeling**: Define strategies and sprints in YAML with task patterns
- 🔌 **Multi-Backend Support**: Integrates with GitHub Issues, Jira, GitLab, and generic HTTP APIs
- 📊 **Progress Tracking**: Review strategy execution with detailed metrics
- 🚀 **CLI Tool**: Easy-to-use command-line interface for applying and reviewing strategies
- 🎨 **Rich Output**: Beautiful terminal output with progress bars and tables
- 🔧 **Extensible**: Easy to add new backends and custom integrations

## Installation

```bash
# Basic installation
pip install strategy

# With all backend integrations
pip install strategy[all]

# Or with specific backends
pip install strategy[github,jira]
```

## Quick Start

### 1. Create a Strategy

Create a `strategy.yaml` file:

```yaml
name: "My Project Strategy"
project_type: "web"
domain: "fintech"
goal: "Launch a secure payment processing platform"

sprints:
  - id: 1
    name: "Core Infrastructure"
    length_days: 14
    objectives:
      - Set up project structure
      - Implement authentication
    tasks:
      - "setup-project"
      - "auth-system"

tasks:
  patterns:
    - id: "setup-project"
      type: "feature"
      title: "Set up project foundation"
      description: "Initialize the project with modern stack"
      priority: "highest"
      estimate: "3d"
      model_hints:
        design: "balanced"
        implementation: "balanced"
```

### 2. Configure Backend

Set up environment variables:

```bash
# For GitHub
export GITHUB_REPO="owner/repo"
export GITHUB_TOKEN="your-token"

# For Jira
export JIRA_URL="https://company.atlassian.net"
export JIRA_EMAIL="your-email@company.com"
export JIRA_TOKEN="your-token"
export JIRA_PROJECT="PROJ"
```

### 3. Apply Strategy

```bash
# Apply strategy (dry run)
strategy apply strategy.yaml . --backend github --dry-run

# Actually create tickets
strategy apply strategy.yaml . --backend github

# Review progress
strategy review strategy.yaml . --backend github
```

## Configuration

### GitHub Integration

```python
from strategy.integrations.github import GitHubBackend

backend = GitHubBackend(
    repo="owner/repo",
    token="your-github-token"
)
```

### Jira Integration

```python
from strategy.integrations.jira import JiraBackend

backend = JiraBackend(
    base_url="https://company.atlassian.net",
    email="your-email@company.com",
    token="your-api-token",
    project="PROJ"
)
```

### GitLab Integration

```python
from strategy.integrations.gitlab import GitLabBackend

backend = GitLabBackend(
    url="https://gitlab.com",
    token="your-gitlab-token",
    project_id=123
)
```

## Python API

```python
from strategy import Strategy, apply_strategy, review_strategy
from strategy.integrations.github import GitHubBackend

# Load strategy
strategy = Strategy.model_validate_yaml("strategy.yaml")

# Set up backend
backend = GitHubBackend(repo="owner/repo", token="token")
backends = {"default": backend}

# Apply strategy
results = apply_strategy(
    strategy=strategy,
    project_path=".",
    backends=backends
)

# Review progress
review = review_strategy(
    strategy=strategy,
    project_path=".",
    backends=backends
)
```

## CLI Commands

### Apply Strategy

```bash
strategy apply STRATEGY_FILE PROJECT_PATH [OPTIONS]

Options:
  --backend TEXT     Backend type [github|jira|gitlab|generic] (default: github)
  --config-file PATH Backend configuration file (JSON)
  --dry-run         Simulate without creating tickets
  --sprint-filter TEXT  Comma-separated sprint IDs to process
  --output PATH     Save results to file
  --verbose         Enable verbose output
```

### Review Strategy

```bash
strategy review STRATEGY_FILE PROJECT_PATH [OPTIONS]

Options:
  --backend TEXT     Backend type [github|jira|gitlab|generic] (default: github)
  --config-file PATH Backend configuration file (JSON)
  --output PATH     Save results to file
  --verbose         Enable verbose output
```

### Validate Strategy

```bash
strategy validate STRATEGY_FILE [OPTIONS]

Options:
  --verbose         Show detailed validation results
```

## Strategy Schema

### Strategy Fields

- `name`: Strategy name (required)
- `project_type`: Type of project (e.g., "web", "mobile", "api")
- `domain`: Business domain (e.g., "fintech", "healthcare")
- `goal`: Main goal of the strategy
- `sprints`: List of sprints
- `tasks`: Task patterns by category
- `quality_gates`: Quality gate definitions
- `success_metrics`: Success criteria

### Sprint Fields

- `id`: Sprint number (required)
- `name`: Sprint name (required)
- `length_days`: Sprint duration in days (default: 14)
- `objectives`: List of sprint objectives
- `start_date`: Start date (ISO format)
- `tasks`: List of task pattern IDs

### Task Pattern Fields

- `id`: Unique identifier (required)
- `type`: Task type (feature, tech_debt, bug, chore, documentation)
- `title`: Task title template (required)
- `description`: Task description template (required)
- `priority`: Default priority (lowest, low, medium, high, highest)
- `estimate`: Time estimate (e.g., "3d", "1w")
- `labels`: Default labels
- `model_hints`: AI model hints for different phases

## Examples

Check the `examples/` directory for complete strategy examples:

- [Onboarding Strategy](strategy/examples/strategies/onboarding.yaml)
- [E-commerce MVP](strategy/examples/strategies/ecommerce-mvp.yaml)
- [Common Tasks](strategy/examples/tasks/common-tasks.yaml)

## Integration with LLX

The `strategy` package is designed to work seamlessly with `llx`:

1. **LLX generates strategy**: Use LLM to generate `strategy.yaml` and `tasks.yaml`
2. **Strategy applies**: Call `strategy apply` to create tickets in external systems
3. **Strategy reviews**: Use `strategy review` to track progress
4. **LLX analyzes**: Feed results back to LLM for analysis and adjustments

## Development

```bash
# Clone repository
git clone https://github.com/wronai/strategy.git
cd strategy

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black strategy/
isort strategy/

# Type checking
mypy strategy/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
