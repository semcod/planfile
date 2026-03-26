# Automated Planfile Generation System

## Overview

Created a complete automated system for generating `planfile.yaml` based on project analysis results from three tools:
- **code2llm** - Cyclomatic complexity analysis
- **vallm** - Validation and linting  
- **redup** - Code duplication detection

## Components Created

### 1. Core Generator (`generate_planfile.py`)
- Parses analysis results from all three tools
- Generates comprehensive planfile with sprints, tasks, and tickets
- Handles missing tools gracefully with mock data
- Customizable generation logic

### 2. Shell Script (`auto_generate_planfile.sh`)
- Runs the complete analysis pipeline
- Executes all three tools in sequence
- Shows summary statistics
- Validates generated planfile

### 3. CLI Tool (`planfile_gen`)
- User-friendly command interface
- Options for mock data, validation, and applying
- Interactive prompts for validation and application
- Non-interactive mode support

### 4. Documentation (`GENERATE_README.md`)
- Complete usage instructions
- Algorithm explanation
- Customization guide
- Troubleshooting tips

## Usage

### Quick Start
```bash
# Generate with mock data (fast)
./planfile_gen --mock

# Run full analysis pipeline
./auto_generate_planfile.sh

# Generate only
python3 generate_planfile.py

# Validate existing planfile
./planfile_gen --validate-only

# Apply planfile (dry run)
./planfile_gen --apply --backend github
```

### Advanced Usage
```bash
# Custom project path
python3 generate_planfile.py --project-path /path/to/project

# Custom output filename
python3 generate_planfile.py --output my-strategy.yaml

# Different backend
./planfile_gen --apply --backend jira
```

## Algorithm Flow

1. **Analysis Phase**
   - Run code2llm → Get CC metrics and high-CC functions
   - Run vallm → Get validation errors and warnings
   - Run redup → Get duplication groups

2. **Generation Phase**
   - Create 3 sprints (Critical, Quality, Polish)
   - Generate tasks based on issues found
   - Create tickets with priorities
   - Set quality gates based on metrics

3. **Output Phase**
   - Save planfile.yaml
   - Validate structure
   - Optional dry-run application

## Generated Strategy Features

### Sprints
- **Sprint 1**: Fix critical issues (errors, high-CC, duplicates)
- **Sprint 2**: Improve quality (warnings, test coverage)
- **Sprint 3**: Polish and release (performance, docs)

### Tasks
- Critical refactors for high-CC functions
- Standard refactors for duplication
- Test writing for coverage
- Documentation for maintainability

### Quality Gates
- Average CC ≤ 3.5
- 0 validation errors
- 0 high-CC functions
- Test coverage ≥ 80%
- 0 code duplication

### Tickets
- High priority: Errors and critical complexity
- Medium priority: Warnings and testing
- Low priority: Documentation and optimization

## Benefits

1. **Automated** - No manual strategy creation
2. **Data-driven** - Based on actual project metrics
3. **Comprehensive** - Covers all quality aspects
4. **Customizable** - Easy to modify generation logic
5. **Integrated** - Works seamlessly with planfile CLI

## Integration with Planfile

The generated planfile works with all planfile commands:
```bash
# Validate
python3 -m planfile.cli.commands validate planfile.yaml

# Apply (dry run)
python3 -m planfile.cli.commands apply planfile.yaml . --dry-run

# Apply to real backend
python3 -m planfile.cli.commands apply planfile.yaml . --backend github

# Review progress
python3 -m planfile.cli.commands review planfile.yaml .
```

## Next Steps

1. Install analysis tools:
   ```bash
   pip install code2llm vallm redup
   ```

2. Run generation:
   ```bash
   ./auto_generate_planfile.sh
   ```

3. Review and customize generated planfile

4. Execute strategy using planfile CLI

5. Track progress and iterate

The system provides a complete end-to-end solution for automated project improvement planning!
