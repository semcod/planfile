# Code2LLM Integration Example

This example demonstrates how to integrate planfile with code2llm to turn code analysis tasks into actionable tickets.

## Overview

Code2LLM is a code analysis tool that identifies technical debt, refactoring opportunities, and improvement tasks. This integration shows how to:

1. Initialize a planfile project
2. Import tasks from code2llm's evolution.toon output
3. Manage technical debt tickets in sprints
4. Track progress on code improvements

## Files in this Example

- `evolution.toon` - Sample code2llm output with refactoring tasks
- `run.sh` - Demonstration script showing the full pipeline
- `README.md` - This documentation

## Prerequisites

1. Install planfile:
   ```bash
   pip install -e .
   ```

2. Install code2llm (optional for generating new analysis):
   ```bash
   pip install code2llm
   # or
   npm install -g code2llm
   ```

## Running the Example

### Quick Start

```bash
cd examples/code2llm
./run.sh
```

This will:
- Initialize a new planfile project
- Create sample tickets
- Import tasks from evolution.toon
- Show the current sprint state

### Manual Steps

1. **Initialize planfile**:
   ```bash
   planfile init --name "Code2LLM Demo" --prefix "C2L"
   ```

2. **Create test tickets**:
   ```bash
   planfile ticket create "Test ticket" --priority normal
   ```

3. **List tickets**:
   ```bash
   planfile ticket list
   ```

4. **Import from code2llm**:
   ```bash
   planfile ticket import --from evolution.toon --source code2llm --sprint backlog
   ```

5. **Move tickets to current sprint**:
   ```bash
   planfile ticket move C2L-001 --to current
   ```

## Understanding evolution.toon

The evolution.toon file contains code analysis results in this format:

```
NEXT[
[H/L] Refactor authentication module
WHY: Current implementation has high cyclomatic complexity (CC=25)
EFFORT: 3 days
IMPACT: 8000
]
```

Each task includes:
- **Priority**: H/L (High/Low effort vs High/Low impact)
- **Title**: Brief description of the task
- **WHY**: Reason for the change
- **EFFORT**: Estimated time required
- **IMPACT**: Business impact score

## Priority Mapping

Code2LLM priorities are mapped to planfile priorities:

| Code2LLM | Planfile | Description |
|----------|----------|-------------|
| H/H      | critical | High effort, high impact |
| H/L      | high     | High effort, low impact |
| L/H      | high     | Low effort, high impact |
| L/L      | normal   | Low effort, low impact |

## Generating New Analysis

To generate a fresh evolution.toon from your code:

```bash
code2llm . -f toon,evolution
```

This will analyze the current directory and create an evolution.toon file with identified tasks.

## Quality Metrics

The example targets these quality metrics:

- **CC̄ ≤ 3.0**: Average cyclomatic complexity should be 3.0 or less
- **Vallm ≥ 95%**: Code validation score should be 95% or higher
- **0 god modules**: No modules with excessive complexity

## Workflow Integration

### 1. Regular Analysis
Run code2llm regularly (e.g., weekly) to identify new technical debt:

```bash
# Weekly cron job
0 9 * * 1 cd /path/to/project && code2llm . -f toon,evolution && planfile ticket import --from evolution.toon --source code2llm --sprint backlog
```

### 2. Sprint Planning
During sprint planning, review imported tasks:

```bash
# Review all technical debt
planfile ticket list --labels technical-debt

# Prioritize high-impact items
planfile ticket list --priority critical,high
```

### 3. Progress Tracking
Track technical debt reduction:

```bash
# Show completed refactoring
planfile ticket list --status done --source code2llm

# Generate metrics report
planfile stats
```

## Best Practices

1. **Regular Analysis**: Run code2llm consistently to track technical debt
2. **Prioritize Impact**: Focus on high-impact, low-effort tasks first (L/H)
3. **Track Trends**: Monitor CC̄ over time to ensure code quality improves
4. **Team Collaboration**: Use planfile to assign tasks to team members
5. **Documentation**: Update WHY clauses with business context

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/technical-debt.yml
name: Technical Debt Analysis
on:
  schedule:
    - cron: '0 9 * * 1'  # Weekly
jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run code2llm
        run: |
          pip install code2llm
          code2llm . -f toon,evolution
      - name: Import to planfile
        run: |
          pip install planfile
          planfile ticket import --from evolution.toon --source code2llm --sprint backlog
```

## Troubleshooting

### No tasks imported
- Check that evolution.toon has a NEXT[] section
- Verify tasks have valid H/L priority format
- Ensure planfile is initialized

### Duplicate tickets
- Use unique identifiers in task titles
- Check existing tickets before importing
- Use `--merge` flag if available

### Priority not set correctly
- Verify H/L format in evolution.toon
- Check for spaces around the slash
- Ensure WHY field is present

## Advanced Usage

### Custom Priority Mapping
Create a custom mapping in planfile.yaml:

```yaml
importers:
  code2llm:
    priority_map:
      "H/H": "critical"
      "H/L": "high"
      "L/H": "high"
      "L/L": "normal"
      "M/M": "low"  # Custom medium priority
```

### Filtering Tasks
Import only specific types of tasks:

```bash
# Import only high-impact tasks
grep -E "H/H|L/H" evolution.toon > high-impact.toon
planfile ticket import --from high-impact.toon --source code2llm --sprint backlog
```

### Multiple Projects
Analyze multiple projects and import to one planfile:

```bash
for project in project1 project2 project3; do
    cd $project
    code2llm . -f toon,evolution
    cd ../planfile
    planfile ticket import --from ../$project/evolution.toon --source code2llm --sprint backlog
done
```

## Related Examples

- `../vallm/` - Import validation errors as tickets
- `../github/` - Sync tickets with GitHub Issues
- `../multi-ticket/` - Route tickets to multiple systems
