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
└── run_all_tests.sh           # Master test runner
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
# For OpenRouter (free LLM validation)
export OPENROUTER_API_KEY=your_key_here

# For various backends (optional)
export GITHUB_TOKEN=your_github_token
export JIRA_URL=your_jira_url
export JIRA_EMAIL=your_email
export JIRA_TOKEN=your_jira_token
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
