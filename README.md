# Planfile

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI version](https://img.shields.io/pypi/v/planfile.svg)](https://pypi.org/project/planfile/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/planfile)](https://pypi.org/project/planfile/)
[![CI/CD](https://github.com/semcod/planfile/workflows/CI%2FCD%20with%20Auto%20Bug-Fix%20Loop/badge.svg)](https://github.com/semcod/planfile/actions)
[![Code Coverage](https://img.shields.io/codecov/c/github/semcod/planfile)](https://codecov.io/gh/semcod/planfile)
[![Code Quality](https://img.shields.io/codecov/c/github/semcod/planfile)](https://codecov.io/gh/semcod/planfile)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![MyPy](https://img.shields.io/badge/mypy-checked-blue)](https://mypy.readthedocs.io/)
[![Pydantic](https://img.shields.io/badge/pydantic-v2-blue)](https://pydantic.dev)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen)](https://strategy.readthedocs.io)
[![GitHub Issues](https://img.shields.io/github/issues/semcod/planfile)](https://github.com/semcod/planfile/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/semcod/planfile)](https://github.com/semcod/planfile/pulls)
[![GitHub Stars](https://img.shields.io/github/stars/semcod/planfile)](https://github.com/semcod/planfile/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/semcod/planfile)](https://github.com/semcod/planfile/network)
[![Last Commit](https://img.shields.io/github/last-commit/semcod/planfile)](https://github.com/semcod/planfile/commits/main)
[![Release Date](https://img.shields.io/github/release-date/semcod/planfile)](https://github.com/semcod/planfile/releases)
[![Project Status](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/semcod/planfile)

**Planfile** is an SDLC automation platform that provides strategic project management with CI/CD integration and automated bug-fix loops. It manages sprints and strategies across external ticket systems like GitHub, Jira, and GitLab.

## ✨ Features

- 🎯 **Strategy Modeling**: Define strategies and sprints in YAML with task patterns
- 🔄 **Automated CI/CD Loop**: Test → Ticket → Fix → Retest automation
- 🔌 **Multi-Backend Support**: Integrates with GitHub Issues, Jira, GitLab, and generic HTTP APIs
- 🤖 **LLM-Powered**: AI-driven bug reports and auto-fix capabilities
- 📊 **Progress Tracking**: Review strategy execution with detailed metrics
- 🚀 **CLI Tool**: Easy-to-use command-line interface for applying and reviewing strategies
- 🎨 **Rich Output**: Beautiful terminal output with progress bars and tables
- 🐳 **Docker Support**: Containerized deployment with Ollama integration
- 🔧 **Extensible**: Easy to add new backends and custom integrations

## 📦 Installation

```bash
# Basic installation
pip install planfile

# With all backend integrations
pip install planfile[all]

# Or with specific backends
pip install planfile[github,jira]
pip install planfile[gitlab]
```

## 🚀 Quick Start

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
      - type: "feature"
        title: "Setup project structure"
        description: "Create basic project layout and configuration"
        estimate: 2
        priority: "high"

  - id: 2
    name: "Payment Processing"
    length_days: 21
    objectives:
      - Implement payment gateway
      - Add security measures
    tasks:
      - type: "feature"
        title: "Payment gateway integration"
        description: "Integrate with payment provider API"
        estimate: 5
        priority: "critical"
```

### 2. Configure Environment

```bash
# GitHub
export GITHUB_TOKEN=your_token
export GITHUB_REPO=owner/repo

# Jira
export JIRA_URL=https://company.atlassian.net
export JIRA_EMAIL=your@email.com
export JIRA_TOKEN=your_token
export JIRA_PROJECT=PROJ

# GitLab
export GITLAB_TOKEN=your_token
export GITLAB_PROJECT_ID=123
```

### 3. Run CI/CD Auto-Loop

```bash
# Run automated bug-fix loop
planfile auto loop \
  --strategy ./strategy.yaml \
  --project . \
  --backend github \
  --max-iterations 5 \
  --auto-fix

# Check CI status
planfile auto ci-status

# Review strategy progress
planfile strategy review \
  --strategy ./strategy.yaml \
  --project . \
  --backend github
```

### 4. Using Makefile

```bash
# Run CI loop with strategy
make ci-loop STRATEGY=strategy.yaml BACKENDS=github MAX_ITERATIONS=5

# Run examples
make example-github
make example-jira

# Full pipeline
make pipeline-docker
```

## 🔄 CI/CD Automation

Planfile provides complete automation for the bug-fix lifecycle:

1. **Test Execution**: Run your test suite
2. **Bug Detection**: Identify failing tests and code issues
3. **AI Analysis**: Generate detailed bug reports using LLM
4. **Ticket Creation**: Create tickets in your PM system
5. **Auto-Fix**: Optionally fix bugs automatically with AI
6. **Verification**: Re-run tests to verify fixes
7. **Loop**: Repeat until all tests pass

## 🐳 Docker Support

```bash
# Build Docker image
make docker-build

# Run with Docker Compose
docker-compose up -d

# Run auto-loop in container
docker-compose exec sprintstrat-runner planfile auto loop \
  --strategy /app/strategy.yaml \
  --project /workspace \
  --backend github \
  --max-iterations 5
```

## 📚 Documentation

- [CI/CD Integration Guide](docs/CI_CD_INTEGRATION.md)
- [API Reference](docs/API.md)
- [Examples](examples/)

## 🔧 Configuration

### Strategy Schema

The `strategy.yaml` file supports:

- **Sprints**: Time-boxed development periods
- **Task Patterns**: Reusable task templates
- **Quality Gates**: Definition of done criteria
- **Success Metrics**: KPIs for strategy completion

### Backend Configuration

Each backend requires specific configuration:

```yaml
# GitHub backend
github:
  token: ${GITHUB_TOKEN}
  repo: ${GITHUB_REPO}

# Jira backend
jira:
  url: ${JIRA_URL}
  email: ${JIRA_EMAIL}
  token: ${JIRA_TOKEN}
  project: ${JIRA_PROJECT}
```

## 🤖 AI Integration

Planfile integrates with LLM services for:

- **Bug Analysis**: Detailed error analysis and root cause identification
- **Auto-Fix**: Automatic code generation for bug fixes
- **Strategy Optimization**: AI-powered recommendations for strategy improvements

```bash
# Enable AI features
export OPENAI_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key

# Run with auto-fix
planfile auto loop --strategy strategy.yaml --auto-fix
```

## 📊 Examples

### Web Project Strategy

```yaml
name: "E-commerce MVP"
project_type: "web"
domain: "ecommerce"
goal: "Launch minimum viable e-commerce platform"

sprints:
  - id: 1
    name: "Foundation"
    length_days: 10
    tasks:
      - type: "feature"
        title: "Setup project structure"
        estimate: 1
      - type: "feature"
        title: "Database schema"
        estimate: 3
```

### Mobile App Strategy

```yaml
name: "Mobile App MVP"
project_type: "mobile"
domain: "healthcare"
goal: "Launch health tracking mobile app"

sprints:
  - id: 1
    name: "Core Features"
    length_days: 14
    tasks:
      - type: "feature"
        title: "User authentication"
        estimate: 3
      - type: "feature"
        title: "Health data tracking"
        estimate: 5
```

## 🔗 Integrations

### Version Control

- **GitHub**: Issues, Projects, Actions
- **GitLab**: Issues, CI/CD, Merge Requests
- **Bitbucket**: Issues, Pipelines

### Project Management

- **Jira**: Issues, Epics, Sprints
- **Linear**: Issues, Projects, Teams
- **ClickUp**: Tasks, Lists, Spaces
- **Asana**: Tasks, Projects, Portfolios

### CI/CD Platforms

- **GitHub Actions**: Workflow automation
- **GitLab CI**: Pipeline integration
- **Jenkins**: Build automation
- **Azure DevOps**: Release management

## 🛠️ Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/semcod/strategy
cd strategy

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check src/ tests/
ruff format src/ tests/
```

### Project Structure

```
strategy/
├── strategy/           # Main package
│   ├── cli/           # CLI commands
│   ├── integrations/  # Backend integrations
│   ├── loaders/       # YAML/JSON loaders
│   └── utils/         # Utilities
├── examples/           # Example strategies
├── tests/             # Test suite
├── docs/              # Documentation
└── docker/            # Docker files
```

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📞 Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/semcod/strategy/issues)
- 💬 [Discussions](https://github.com/semcod/strategy/discussions)

## 🏆 Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/) for CLI
- Styled with [Rich](https://rich.readthedocs.io/) for terminal output
- Validated with [Pydantic](https://pydantic-docs.helpmanual.io/) for data models

---

**Planfile** - Your strategic partner in SDLC automation. 🚀

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
