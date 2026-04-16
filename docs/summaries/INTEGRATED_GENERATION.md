## Overview

The planfile package now includes built-in functionality to generate comprehensive strategies directly from code analysis. This integration eliminates the need for external scripts and provides a seamless workflow for creating improvement plans.

### Usage
```bash
python3 -m planfile.cli.commands generate-from-files [PROJECT_PATH] [OPTIONS]
```

### Options
- `--output TEXT`: Output file path (default: planfile-from-files.yaml)
- `--project-name TEXT`: Custom project name (default: auto-detected)
- `--max-sprints INTEGER`: Maximum number of sprints (default: 4)
- `--focus TEXT`: Focus area - quality, security, performance, testing, documentation
- `--patterns TEXT`: File patterns to analyze (default: *.yaml, *.yml, *.json, *.toon.yaml, *.toon.yml)
- `--verbose`: Enable verbose output

# Analyze current directory
python3 -m planfile.cli.commands generate-from-files .

# Analyze specific directory
python3 -m planfile.cli.commands generate-from-files ./src

# Custom output file
python3 -m planfile.cli.commands generate-from-files . --output my-strategy.yaml
```

# Focus on security improvements
python3 -m planfile.cli.commands generate-from-files . --focus security

# Limit to 2 sprints
python3 -m planfile.cli.commands generate-from-files . --max-sprints 2

# Analyze specific file types
python3 -m planfile.cli.commands generate-from-files . --patterns "*.py" "*.yaml"

# Verbose output
python3 -m planfile.cli.commands generate-from-files . --verbose
```

### Direct Usage
```python
from planfile.analysis.generator import generator

# Generate from current project
strategy = generator.generate_from_current_project(
    project_path=".",
    project_name="my-project",
    max_sprints=4,
    focus_area="quality"
)

# Save strategy
from planfile.loaders.yaml_loader import save_strategy_yaml
save_strategy_yaml(strategy, "my-strategy.yaml")
```

### Custom Analysis
```python
from planfile.analysis.file_analyzer import FileAnalyzer
from planfile.analysis.sprint_generator import SprintGenerator

# Analyze files
analyzer = FileAnalyzer()
result = analyzer.analyze_directory(Path("./project"))

# Generate sprints
sprint_gen = SprintGenerator()
sprints = sprint_gen.generate_sprints(result)
tickets = sprint_gen.generate_tickets(result)
```

### Analysis Formats
- **Toon files** (.toon.yaml, .toon.yml) - Output from code2llm, vallm, redup
- **YAML files** (.yaml, .yml) - Configuration, documentation
- **JSON files** (.json) - Configuration, data files

### Extracted Information
- **Issues**: TODO, FIXME, BUG, HACK, OPTIMIZE, REFACTOR comments
- **Metrics**: Cyclomatic complexity, test coverage, error counts
- **Code patterns**: Duplication, long functions, validation errors

### code2llm Integration
Extracts from analysis.toon.yaml:
- Average cyclomatic complexity
- Critical functions (CC > 15)
- High-CC function list
- Refactoring recommendations

### vallm Integration
Extracts from validation.toon.yaml:
- Validation errors and warnings
- File-specific issues
- Pass/fail rates
- Quality metrics

### redup Integration
Extracts from duplication.toon.yaml:
- Duplication groups
- Lines saved by deduplication
- Specific duplicate functions
- Extraction opportunities

### Automatic Goals
Based on analysis results:
- Fix critical issues
- Reduce complexity
- Remove duplication
- Improve test coverage
- Address validation errors

### Quality Gates
Automatically configured:
- Average CC ≤ 3.5
- Zero critical functions
- Zero validation errors
- Zero duplication groups
- Test coverage ≥ 80%

### Sprint Organization
Issues organized by priority:
1. **Critical Issues** - Bugs and errors
2. **Quality & High Priority** - Refactoring and improvements
3. **Feature Development** - Medium priority tasks
4. **Polish & Documentation** - Low priority items

### Ticket Generation
Each issue becomes a ticket with:
- Title and description
- Priority and category
- File path and line number
- Effort estimate
- Relevant tags

## Module Structure

```
planfile/
├── analysis/
│   ├── __init__.py
│   ├── file_analyzer.py      # File analysis engine
│   ├── sprint_generator.py   # Sprint and ticket generation
│   └── generator.py          # Main generator class
└── cli/
    └── commands.py           # CLI command integration
```

### FileAnalyzer Class
- Parses various file formats
- Extracts issues using pattern matching
- Identifies metrics from tool outputs
- Handles special toon format

### SprintGenerator Class
- Groups issues by priority
- Creates logical sprint structures
- Estimates effort based on complexity
- Generates ticket details

### PlanfileGenerator Class
- Coordinates analysis and generation
- Creates complete strategy objects
- Handles focus areas and customization
- Provides Python API

# Weekly analysis
python3 -m planfile.cli.commands generate-from-files . --output weekly-plan.yaml
```

# Security focus
python3 -m planfile.cli.commands generate-from-files . --focus security

# Performance focus
python3 -m planfile.cli.commands generate-from-files . --focus performance
```

# GitHub Actions
- name: Generate Improvement Plan
  run: |
    python3 -m planfile.cli.commands generate-from-files . \
      --output ci-plan.yaml \
      --focus quality
```

# Analyze specific directories
python3 -m planfile.cli.commands generate-from-files ./src \
  --patterns "*.py" "*.yaml" \
  --max-sprints 2
```

### Common Issues

**No files analyzed**
- Check file patterns match your files
- Ensure directory contains supported formats

**Too many issues**
- Use `--max-sprints` to limit scope
- Focus on specific area with `--focus`

**Validation errors**
- Generated planfiles may need manual adjustment
- Use `--dry-run` to review before applying

# Enable verbose output
python3 -m planfile.cli.commands generate-from-files . --verbose
```

# Generate and validate
python3 -m planfile.cli.commands generate-from-files . --output quick-check.yaml
python3 -m planfile.cli.commands validate quick-check.yaml
```

# Focus on security
python3 -m planfile.cli.commands generate-from-files . \
  --focus security \
  --output security-plan.yaml

# Apply to GitHub
python3 -m planfile.cli.commands apply security-plan.yaml . --backend github
```

# Performance focus with custom patterns
python3 -m planfile.cli.commands generate-from-files . \
  --focus performance \
  --patterns "*.py" "*.js" \
  --max-sprints 2 \
  --output perf-plan.yaml
```

## Benefits of Integration

1. **No External Dependencies** - Built into the planfile package
2. **Consistent API** - Same format as other planfile strategies
3. **Flexible Analysis** - Supports multiple file formats
4. **Customizable Focus** - Target specific improvement areas
5. **CI/CD Ready** - Easy to integrate into pipelines
6. **Python API** - Programmatic access for automation

This integration provides a powerful, built-in capability for turning code analysis into actionable improvement strategies!
