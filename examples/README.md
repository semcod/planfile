# Examples Directory

This directory contains test examples and scripts for the planfile project, including ecosystem integrations with LLX, Proxy, and OpenRouter.

## Structure

```
examples/
├── README.md                    # This file
├── test_all_examples.py         # Test runner with LLM validation
├── llx_validator.py             # LLX validation utilities
├── validate_with_llx.sh         # Shell script for validation
├── readme-tests/               # Tests for README examples
│   └── test_readme_examples.sh
├── bash-generation/            # Bash scripts for planfile.yaml generation
│   ├── test_planfile_generation.sh
│   └── verify_planfile.sh
├── interactive-tests/          # Interactive mode tests
│   ├── test_interactive_mode.py
│   └── test_interactive_expect.sh
├── ecosystem/                  # Ecosystem integration examples
│   ├── 01_full_workflow.sh     # Complete workflow: planfile → llx → proxy
│   ├── 02_mcp_integration.py   # MCP tools for LLM agents
│   ├── 03_proxy_routing.py     # Smart model routing with proxy
│   └── 04_llx_integration.py   # Metric-driven planning with LLX
├── strategies/                 # Example strategy files
│   └── simple.yaml
├── tasks/                      # Example task patterns
│   └── common.yaml
├── run_all_tests.sh           # Master test runner
├── quick-start/               # ⚡ Quick start guide (NEW!)
│   ├── README.md
│   ├── run.sh
│   └── quick_start_examples.py
├── integrated-functionality/  # 🚀 Integrated features demo
│   ├── README.md
│   ├── run.sh
│   └── integrated_functionality_examples.py
├── cli-commands/              # 💻 CLI commands showcase
│   ├── README.md
│   ├── run.sh
│   └── cli_command_examples.py
├── external-tools/           # 🔧 External tools integration
│   ├── README.md
│   ├── run.sh
│   └── external_tools_examples.py
└── advanced-usage/           # 🎯 Advanced patterns and workflows
    ├── README.md
    ├── run.sh
    └── advanced_usage_examples.py
```

## Quick Start

### 1. Install Dependencies

```bash
# Core planfile
pip install -e .

# Optional integrations
pip install planfile[all]  # Includes litellm, llx, and all PM backends

# Or install individually
pip install litellm llx PyGithub python-gitlab jira
```

### 2. Set Up API Keys

```bash
# For OpenAI (if using)
export OPENAI_API_KEY=sk-...

# For GitHub backend (if using)
export GITHUB_TOKEN=ghp_...

# For OpenRouter (free LLM validation)
export OPENROUTER_API_KEY=sk-or-v1-...
```

### 3. Run Examples

Each example has its own folder with README and run.sh script:

```bash
# Quick start (beginners)
cd quick-start && ./run.sh

# Integrated functionality (complete overview)
cd integrated-functionality && ./run.sh

# CLI commands (command-line interface)
cd cli-commands && ./run.sh

# External tools (code2llm, vallm, redup)
cd external-tools && ./run.sh

# Advanced usage (power users)
cd advanced-usage && ./run.sh
```

### 3. Run All Examples with Validation

```bash
# Test all examples with LLM validation
python test_all_examples.py

# Or use the shell runner
./run_all_tests.sh
```

## Ecosystem Integration Examples

### 1. Full Workflow (ecosystem/01_full_workflow.sh)

Demonstrates the complete ecosystem flow:
- Generate strategy with planfile
- Analyze with LLX
- Route through Proxy for cost optimization
- Track progress

```bash
./ecosystem/01_full_workflow.sh
```

### 2. MCP Integration (ecosystem/02_mcp_integration.py)

Shows how planfile can be used as MCP tools by LLM agents:
- `planfile_generate`: Create strategies from project analysis
- `planfile_apply`: Execute strategies and create tickets
- `planfile_review`: Track progress and validate completion

```python
python ecosystem/02_mcp_integration.py
```

### 3. Proxy Routing (ecosystem/03_proxy_routing.py)

Demonstrates smart model routing through Proxy:
- Task-based model selection
- Cost optimization
- Budget tracking
- Fallback chains

```python
python ecosystem/03_proxy_routing.py
```

### 4. LLX Integration (ecosystem/04_llx_integration.py)

Shows metric-driven planning using LLX:
- Code analysis and metrics collection
- Optimal model selection based on complexity
- Task scope estimation
- Quality gate definition

```python
python ecosystem/04_llx_integration.py
```

## New Examples (Integrated Functionality)

### ⚡ Quick Start (quick-start/)

Get started with planfile in minutes! This example shows the basics:
- Generate strategy from files
- Create templates
- Load and analyze strategies
- Export to different formats
- Compare strategies

```bash
cd quick-start && ./run.sh
```

### 🚀 Integrated Functionality (integrated-functionality/)

Comprehensive demo of all new integrated features:
- File analysis without external scripts
- Template generation for different project types
- Strategy comparison and merging
- Multiple export formats
- Statistics and health checking

```bash
cd integrated-functionality && ./run.sh
```

### 💻 CLI Commands (cli-commands/)

Shows how to use all new CLI commands:
- `planfile template` - Generate templates
- `planfile stats` - View statistics
- `planfile export` - Export to various formats
- `planfile compare` - Compare strategies
- `planfile health` - Check project health
- `planfile generate-from-files` - Analyze and generate

```bash
cd cli-commands && ./run.sh
```

### 🔧 External Tools (external-tools/)

Integration with external analysis tools:
- code2llm - Code complexity analysis
- vallm - Validation and linting
- redup - Code duplication detection
- Combined analysis with all tools

```bash
# Install tools first
pip install code2llm vallm redup

cd external-tools && ./run.sh
```

### 🎯 Advanced Usage (advanced-usage/)

Advanced patterns and workflows:
- Custom file patterns
- Focus-specific strategies
- Iterative strategy refinement
- Batch processing multiple directories
- Custom metrics integration
- CI/CD workflow automation

```bash
cd advanced-usage && ./run.sh
```

## Validation with LLX

### Automated Validation

The examples include automated validation using LLX:

```bash
# Validate all generated files
./validate_with_llx.sh

# Or use Python validator
python llx_validator.py
```

### LLM Validation with OpenRouter

Free LLM validation using OpenRouter:

```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY=sk-or-v1-...

# Run tests with LLM validation
python test_all_examples.py
```

The validation checks:
- **YAML Structure**: Valid strategy format
- **Code Quality**: Python syntax and best practices
- **Logic Validation**: Task priorities and estimates
- **Security**: Basic security checks

## Individual Tests

### README Examples Test

Tests the CLI commands shown in the README file:

```bash
./readme-tests/test_readme_examples.sh
```

### Planfile Generation Test

Tests planfile.yaml generation with various project structures:

```bash
./bash-generation/test_planfile_generation.sh
```

### Planfile Verification Test

Validates generated planfile.yaml files for correctness:

```bash
./bash-generation/verify_planfile.sh
```

### Interactive Mode Tests

Python-based test:
```bash
./interactive-tests/test_interactive_mode.py
```

Expect-based test (requires expect):
```bash
./interactive-tests/test_interactive_expect.sh
```

## Test Coverage

The examples test:

1. **README Examples**: All CLI commands demonstrated in the README
2. **Planfile Generation**: 
   - Default generation
   - Custom configuration
   - Complex project structures
   - Generation consistency
3. **Planfile Verification**:
   - YAML syntax validation
   - Required sections check
   - Content structure validation
4. **Interactive Mode**:
   - Basic interactive input
   - Custom data input
   - Repeatable generation
   - Error handling
5. **Ecosystem Integration**:
   - LLX metric-driven planning
   - Proxy smart routing
   - MCP tool integration
   - Full workflow automation

## Prerequisites

- planfile command installed (`pip install -e .` from project root)
- Python 3.10+
- Optional: expect (for interactive tests)
- Optional: LLX (for advanced validation)
- Optional: OpenRouter API key (for LLM validation)

Install optional dependencies:
```bash
# LLX for code analysis
pip install llx

# Expect for interactive tests
# Ubuntu/Debian: sudo apt-get install expect
# macOS: brew install expect
# RHEL/CentOS: sudo yum install expect
```

## Output

Each test generates:
- Console output with test progress
- Log files in respective test directories
- Generated planfile.yaml examples
- Validation reports (test-results.json)

## Example Generated Strategy

## Quick Reference

### New CLI Commands
```bash
# Generate template
planfile template web ecommerce

# Generate from files
planfile generate-from-files . --focus quality

# View statistics
planfile stats strategy.yaml

# Export formats
planfile export strategy.yaml --format html
planfile export strategy.yaml --format csv

# Compare strategies
planfile compare old.yaml new.yaml

# Health check
planfile health .
```

### Python API
```python
from planfile import Strategy
from planfile.analysis.generator import generator

# Generate from analysis
strategy = generator.generate_from_current_project(".")

# Create template
from planfile.cli.extra_commands import generate_template
template = generate_template("web", "ecommerce")

# Load and analyze
s = Strategy.load("strategy.yaml")
stats = s.get_stats()

# Compare
comparison = s1.compare(s2)

# Export
yaml_data = s.export("yaml")
json_data = s.export("json")
```

### Example Files Generated

Each example folder generates its own set of files:

**quick-start/**
- `quick-start.yaml` - Basic generated strategy
- `web-template.yaml` - Web project template
- `web-template.json` - Template in JSON format

**integrated-functionality/**
- `generated-from-examples.yaml` - Strategy from file analysis
- `template-*.yaml` - Project templates (web, mobile, ml)
- `strategy-export.*` - Various export formats
- `merged-strategy.yaml` - Combined strategy

**cli-commands/**
- `cli-example-*.yaml` - Generated strategies
- `cli-example-*.json` - JSON exports
- `cli-example.html` - HTML report

**external-tools/**
- `*.toon.yaml` - External tool outputs (if tools installed)
- `external-tools-generated.yaml` - Strategy from external analysis
- `quality-focused.yaml` - Quality-focused strategy

**advanced-usage/**
- `custom-patterns-strategy.yaml` - Custom analysis strategy
- `focus-*-strategy.yaml` - Focus-specific strategies
- `iterative-*.yaml` - Strategy versions
- `batch-*-strategy.yaml` - Batch processing results
- `ci-workflow.sh` - Generated CI/CD script

## Tips
1. Start with `cd quick-start && ./run.sh` for basics
2. Use `cd integrated-functionality && ./run.sh` for complete overview
3. Install external tools for deeper analysis: `pip install code2llm vallm redup`
4. Each example has its own README with detailed information
5. Check generated YAML files to understand structure
6. Use `./run.sh` in each folder for easy execution

```yaml
project:
  name: "my-project"
  focus: "complexity"
  metrics:
    total_files: 25
    avg_cc: 6.2
    max_cc: 18

sprints:
  - id: sprint-1
    name: "Critical Fixes"
    goal: "Reduce complexity in god modules"
    task_patterns:
      - name: "Split god module (CC=18)"
        task_type: "refactor"
        priority: "critical"
        model_hints:
          planning: "premium"
          implementation: "balanced"

quality_gates:
  - name: "Complexity Gate"
    metric: "avg_cc"
    threshold: 3.0
    operator: "<="
```

## Troubleshooting

If tests fail:
1. Check that planfile is installed: `which planfile`
2. Verify Python version: `python3 --version`
3. Check test log files for detailed errors
4. Run individual tests to isolate issues
5. For LLM validation, check OpenRouter API key

### Common Issues

1. **LLX not found**
   ```bash
   pip install llx
   ```

2. **Proxy not running**
   ```bash
   docker run -p 4000:4000 proxym/proxy
   ```

3. **OpenRouter API key**
   - Get free key at: https://openrouter.ai/keys
   - Set environment variable: `export OPENROUTER_API_KEY=...`

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Planfile   │────▶│     LLX     │────▶│    Proxy    │
│             │     │             │     │             │
│ - Strategy  │     │ - Analysis  │     │ - Routing   │
│ - Tasks     │     │ - Metrics   │     │ - Budget    │
│ - Gates     │     │ - Models    │     │ - Cache     │
└─────────────┘     └─────────────┘     └─────────────┘
```

Each tool plays a specific role:
- **Planfile**: Strategy definition and orchestration
- **LLX**: Code analysis and model selection
- **Proxy**: Smart routing and cost optimization
