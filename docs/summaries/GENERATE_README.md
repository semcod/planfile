# Automated Planfile Generation

This directory contains tools to automatically generate `planfile.yaml` based on project analysis results.

## Overview

The automated generation algorithm:
1. Runs `code2llm` for cyclomatic complexity analysis
2. Runs `vallm` for validation and linting
3. Runs `redup` for code duplication detection
4. Generates a comprehensive planfile based on the results

## Files

### `generate_planfile.py`
Python script that parses analysis results and generates planfile.yaml.

**Usage:**
```bash
# Run with actual analysis tools
python3 generate_planfile.py

# Use mock data (for testing)
python3 generate_planfile.py --mock

# Specify custom output
python3 generate_planfile.py --output my-strategy.yaml
```

**Options:**
- `--project-path`: Path to analyze (default: current directory)
- `--output`: Output filename (default: planfile.yaml)
- `--mock`: Use mock data instead of running analysis

### `auto_generate_planfile.sh`
Shell script that runs the complete pipeline including analysis tools.

**Usage:**
```bash
# Run full pipeline
./auto_generate_planfile.sh

# Specify project path
./auto_generate_planfile.sh /path/to/project
```

## Prerequisites

Install the analysis tools:
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install tools
pip install code2llm vallm redup
```

## Algorithm Details

### 1. Analysis Phase

**code2llm** extracts:
- Cyclomatic complexity metrics
- High-CC functions (CC > 15)
- Code structure and dependencies

**vallm** validates:
- Syntax errors
- Import resolution
- Code style warnings
- Function length violations

**redup** finds:
- Duplicate code blocks
- Potential extraction opportunities
- Lines that could be saved

### 2. Generation Phase

Based on analysis results, the generator creates:

#### Sprints
- **Sprint 1**: Critical issues (errors, high-CC functions, duplicates)
- **Sprint 2**: Quality improvements (warnings, test coverage)
- **Sprint 3**: Polish and release (performance, documentation)

#### Tasks
- **Critical Refactors**: High-CC functions
- **Standard Refactors**: Code duplication
- **Test Writing**: Unit and integration tests
- **Documentation**: API docs and examples

#### Quality Gates
- Average CC ≤ 3.5
- 0 validation errors
- 0 high-CC functions
- Test coverage ≥ 80%
- 0 code duplication

#### Tickets
- **High Priority**: Errors and critical complexity
- **Medium Priority**: Warnings and test coverage
- **Low Priority**: Documentation and optimization

## Example Output

Generated planfile includes:
```yaml
name: Project Code Quality Improvement
project_name: myproject
project_type: refactoring
domain: dev-tools
goal: Reduce complexity and improve code quality

sprints:
  - id: sprint-1
    name: Critical Issues Resolution
    duration: 2 weeks
    # ...

tasks:
  critical_refactors:
    - name: "Refactor function_name (CC=20)"
      estimated_hours: 10
      complexity: high
  # ...

tickets:
  high_priority:
    - title: "Fix 5 validation errors"
      priority: highest
  # ...
```

## Integration with Planfile

Once generated:
```bash
# Validate the strategy
python3 -m planfile.cli.commands validate planfile.yaml

# Apply strategy (dry run)
python3 -m planfile.cli.commands apply planfile.yaml . --dry-run

# Apply to real backend
python3 -m planfile.cli.commands apply planfile.yaml . --backend github

# Review progress
python3 -m planfile.cli.commands review planfile.yaml .
```

## Customization

### Adding New Analysis Tools

1. Add parsing function in `generate_planfile.py`:
```python
def parse_my_tool_output(self) -> Dict[str, Any]:
    # Parse your tool's output
    return metrics
```

2. Update the `run()` method to call your tool.

3. Incorporate metrics into `generate_planfile()`.

### Modifying Generation Logic

Edit the generation methods:
- `generate_sprints()`: Define sprint structure
- `generate_tasks()`: Create task breakdowns
- `generate_tickets()`: Define ticket priorities
- `generate_quality_gates()`: Set quality criteria

### Custom Templates

Create custom planfile templates for different project types:
- Feature development
- Security hardening
- Performance optimization
- Documentation updates

## Troubleshooting

### Tools Not Found
```
⚠️ code2llm not found
```
Install missing tools:
```bash
pip install code2llm vallm redup
```

### No Analysis Results
If tools fail to run, use `--mock` flag to test generation logic.

### Validation Errors
Check generated planfile:
```bash
python3 -m planfile.cli.commands validate planfile.yaml
```

## Best Practices

1. **Run Before Major Releases**: Generate planfile before each release to catch issues.

2. **Customize Thresholds**: Adjust quality gates based on project standards.

3. **Review Generated Tasks**: AI-generated tasks may need manual adjustment.

4. **Track Progress**: Use planfile review to monitor improvement.

5. **Iterate**: Re-run analysis after completing sprints to measure progress.

## Examples

See generated files:
- `planfile.yaml` - Generated strategy
- `planfile-auto.yaml` - Mock data example
- `project/` - Analysis results directory
