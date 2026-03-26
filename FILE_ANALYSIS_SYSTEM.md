# File-Based Planfile Generation System

## Overview

This system automatically generates comprehensive `planfile.yaml` strategies by analyzing YAML/JSON files in your project. It extracts issues, metrics, and tasks from various file formats to create data-driven improvement plans.

## Components

### 1. Enhanced File Analyzer (`enhanced_analyze.py`)
- Analyzes YAML, JSON, and Toon format files
- Extracts TODOs, FIXMEs, bugs, and code metrics
- Supports specialized parsing for analysis tool outputs
- Identifies code complexity, duplication, and validation issues

### 2. Planfile Generator (`generate_from_files.py`)
- Creates complete planfile from analysis results
- Generates sprints based on issue priorities
- Creates tickets with effort estimates
- Defines quality gates and success criteria

### 3. Sprint Generator (included in both)
- Organizes issues into logical sprints
- Prioritizes critical issues first
- Balances workload across sprints
- Estimates effort based on complexity

## Supported File Formats

### Standard Formats
- **YAML (.yaml, .yml)** - Configuration files, documentation
- **JSON (.json)** - Configuration, data files

### Specialized Formats
- **Toon (.toon.yaml, .toon.yml)** - Output from analysis tools:
  - code2llm complexity analysis
  - vallm validation results
  - redup duplication detection

### Extracted Information
- **Issues**: TODOs, FIXMEs, bugs, optimization notes
- **Metrics**: Cyclomatic complexity, test coverage, error counts
- **Tasks**: Refactoring needs, test requirements, documentation

## Usage

### Basic Usage
```bash
# Analyze current directory
python3 generate_from_files.py

# Analyze specific directory
python3 generate_from_files.py ./project

# Custom output file
python3 generate_from_files.py --output my-plan.yaml

# Custom project name
python3 generate_from_files.py --project-name "My Project"
```

### Advanced Options
```bash
# Limit number of sprints
python3 generate_from_files.py --max-sprints 2

# Custom file patterns
python3 generate_from_files.py --patterns "*.yaml" "*.json"

# Analyze only specific directory
python3 enhanced_analyze.py ./analysis --format json
```

## Generated Planfile Structure

### Goals Section
Automatically generated based on found issues:
```yaml
goals:
- Fix all 5 critical issues
- Reduce average CC from 4.2 to ≤ 3.5
- Resolve all validation errors
- Remove code duplication groups
```

### Quality Gates
Set based on current metrics:
```yaml
quality_gates:
- metric: Average Cyclomatic Complexity
  threshold: ≤ 3.5
- metric: Critical Functions
  threshold: 0
- metric: Validation Errors
  threshold: 0
```

### Sprints
Organized by priority:
1. **Critical Issues Sprint** - Fix critical bugs and errors
2. **Quality & High Priority** - Address high-priority issues
3. **Feature Development** - Medium priority improvements
4. **Polish & Documentation** - Low priority tasks

### Tasks
Categorized by type:
```yaml
tasks:
  critical_refactors:
  - name: "Refactor function_name (CC=20)"
    file_path: "src/file.py"
    estimated_hours: 8
  bug_fixes:
  - name: "Fix validation error"
    file_path: "config.yaml"
```

### Tickets
Generated with priorities:
```yaml
tickets:
  critical:
  - title: "Fix critical bug in module"
    description: "Detailed description..."
    priority: critical
    file_path: "src/module.py"
```

## Integration with Analysis Tools

### code2llm Integration
Extracts from `analysis.toon.yaml`:
- Average cyclomatic complexity
- Critical functions (CC > 15)
- High-CC function list
- Refactoring recommendations

### vallm Integration
Extracts from `validation.toon.yaml`:
- Validation errors and warnings
- File-specific issues
- Pass/fail rates
- Quality metrics

### redup Integration
Extracts from `duplication.toon.yaml`:
- Duplication groups
- Lines saved by deduplication
- Specific duplicate functions
- Extraction opportunities

## Example Workflow

### 1. Run Analysis Tools
```bash
# Run code analysis tools
venv/bin/code2llm . -f all -o ./project --no-chunk
venv/bin/vallm batch . --recursive --format toon --output .
venv/bin/redup scan . --format toon --output ./project
```

### 2. Generate Planfile
```bash
# Generate from analysis results
python3 generate_from_files.py ./project --project-name myproject
```

### 3. Validate and Apply
```bash
# Validate generated planfile
python3 -m planfile.cli.commands validate planfile-from-files.yaml

# Apply (dry run)
python3 -m planfile.cli.commands apply planfile-from-files.yaml . --dry-run

# Apply to real backend
python3 -m planfile.cli.commands apply planfile-from-files.yaml . --backend github
```

## Customization

### Adding New File Types
Extend `EnhancedFileAnalyzer`:
```python
def _analyze_custom_format(self, file_path: Path):
    # Parse your custom format
    # Return issues, metrics, tasks
```

### Custom Issue Patterns
Add new patterns in `__init__`:
```python
self.issue_patterns['security'] = re.compile(r'(?i)SECURITY\s*[:#]?\s*(.+)')
```

### Custom Sprint Logic
Modify `generate_sprints()` to create custom sprint structures.

## Best Practices

1. **Regular Analysis**: Run analysis tools weekly to track progress
2. **Review Generated Plans**: AI-generated plans may need manual adjustment
3. **Update Estimates**: Review effort estimates based on team velocity
4. **Track Metrics**: Monitor improvement in quality gates over time
5. **Iterate**: Re-generate planfile after completing sprints

## Troubleshooting

### Common Issues

**"No files analyzed"**
- Check file patterns match your files
- Ensure files are not excluded by filters

**"Parsing errors"**
- Some files may have invalid YAML/JSON
- Analyzer creates issues for these automatically

**"Too many issues"**
- Use `--max-sprints` to limit scope
- Focus on critical and high priority issues first

### Debug Mode
Add debug output to see what's being extracted:
```python
# In enhanced_analyze.py
print(f"Found {len(issues)} issues in {file_path}")
for issue in issues[:5]:
    print(f"  - {issue.title}")
```

## Performance

- Analyzes 100+ files in seconds
- Handles large codebases efficiently
- Memory usage scales with file count
- Can be run on CI/CD pipelines

## Integration Examples

### GitHub Actions
```yaml
- name: Generate Planfile
  run: |
    python3 generate_from_files.py ./analysis --output planfile.yaml
    python3 -m planfile.cli.commands validate planfile.yaml
```

### Pre-commit Hook
```bash
#!/bin/sh
python3 generate_from_files.py --max-sprints 1 --output quick-plan.yaml
```

### CI/CD Pipeline
```bash
# Generate improvement plan
python3 generate_from_files.py --output ci-plan.yaml

# Check if critical issues exist
if [ $(grep -c "priority: critical" ci-plan.yaml) -gt 0 ]; then
  echo "Critical issues found!"
  exit 1
fi
```

This system provides a powerful, automated way to turn file analysis into actionable improvement plans!
