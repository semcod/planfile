# Vallm Integration Example

This example demonstrates how to integrate planfile with vallm to turn validation errors into actionable tickets.

## Overview

Vallm is a code validation tool that identifies issues like:
- Import errors
- Style violations
- Security vulnerabilities
- Performance problems
- Documentation gaps

This integration shows how to:
1. Initialize a planfile project
2. Import validation errors from vallm's validation.toon output
3. Track quality improvements
4. Maintain code quality standards

## Files in this Example

- `validation.toon` - Sample vallm output with validation errors
- `run.sh` - Demonstration script showing the full pipeline
- `README.md` - This documentation

## Prerequisites

1. Install planfile:
   ```bash
   pip install -e .
   ```

2. Install vallm (optional for generating new validation):
   ```bash
   pip install vallm
   # or
   npm install -g vallm
   ```

## Running the Example

### Quick Start

```bash
cd examples/vallm
./run.sh
```

This will:
- Initialize a new planfile project
- Create sample tickets
- Import validation errors to current sprint
- Show quality gates and metrics

### Manual Steps

1. **Initialize planfile**:
   ```bash
   planfile init --name "Vallm Demo" --prefix "VL"
   ```

2. **Create test tickets**:
   ```bash
   planfile ticket create "Test ticket" --priority normal
   ```

3. **List tickets**:
   ```bash
   planfile ticket list
   ```

4. **Import from vallm**:
   ```bash
   planfile ticket import --from validation.toon --source vallm --sprint current
   ```

5. **Update ticket status**:
   ```bash
   planfile ticket update VL-001 --status in-progress
   ```

## Understanding validation.toon

The validation.toon file contains validation results:

```
ERRORS[
planfile/core/store.py,0.85
  python.import.resolvable,error,Module 'deprecated' not found,3
  python.complexity.mccabe,error,Function '_apply_filters' is too complex (CC=15),1
]
```

Each error includes:
- **File**: Path to the file with issues
- **Score**: Quality score (0.0 - 1.0)
- **Rule**: Validation rule that failed
- **Severity**: error, warning, or info
- **Message**: Description of the issue
- **Count**: Number of occurrences

## Priority Mapping

Vallm issues are mapped to planfile priorities based on severity:

| Severity | Planfile | Examples |
|----------|----------|----------|
| error    | critical | Module not found, undefined variable |
| warning  | high     | Style violations, unused imports |
| info     | normal   | Missing documentation |

## Generating New Validation

To generate a fresh validation.toon from your code:

```bash
vallm batch . --recursive
```

This will analyze the current directory recursively and create a validation.toon file.

## Quality Metrics

The example targets these quality metrics:

- **CC̄ ≤ 3.0**: Average cyclomatic complexity should be 3.0 or less
- **Vallm ≥ 95%**: Code validation score should be 95% or higher
- **0 god modules**: No modules with excessive complexity

## Quality Gates

### Critical Issues (Priority: critical)
Must be fixed immediately:
- Module not found errors
- Undefined variable errors
- Security vulnerabilities

### High Priority Issues
Should be fixed in current sprint:
- Code complexity violations
- Import errors
- Performance issues

### Medium Priority Issues
Can be scheduled for next sprint:
- Style violations
- Missing documentation
- Unused imports

## Workflow Integration

### 1. Pre-commit Validation
Add vallm to pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: vallm
        name: vallm validation
        entry: vallm
        language: system
        args: [batch, ., --recursive]
        pass_filenames: false
```

### 2. CI/CD Pipeline
Add to your CI pipeline:

```yaml
# .github/workflows/quality.yml
name: Code Quality
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run vallm
        run: |
          pip install vallm
          vallm batch . --recursive
      - name: Import to planfile
        run: |
          pip install planfile
          planfile ticket import --from validation.toon --source vallm --sprint current
      - name: Check quality gate
        run: |
          # Fail if validation score < 95%
          SCORE=$(grep "average_score" validation.toon | awk '{print $NF}')
          if (( $(echo "$SCORE < 0.95" | bc -l) )); then
            echo "Validation score $SCORE is below 95%"
            exit 1
          fi
```

### 3. Daily Quality Report
Automated daily quality checks:

```bash
# Daily cron job
0 8 * * * cd /path/to/project && vallm batch . --recursive && planfile ticket import --from validation.toon --source vallm --sprint backlog
```

## Best Practices

1. **Fix Critical First**: Always address critical issues immediately
2. **Batch Fixes**: Group similar issues and fix them together
3. **Track Trends**: Monitor validation score over time
4. **Team Ownership**: Assign validation tickets to appropriate team members
5. **Preventive Measures**: Add linters and formatters to prevent common issues

## Advanced Usage

### Custom Priority Mapping
Configure custom priority rules in planfile.yaml:

```yaml
importers:
  vallm:
    priority_rules:
      "python.import.resolvable": "critical"
      "python.security.*": "critical"
      "python.complexity.*": "high"
      "python.style.*": "normal"
```

### Filtering Issues
Import only specific types of issues:

```bash
# Import only security issues
grep "security" validation.toon > security.toon
planfile ticket import --from security.toon --source vallm --sprint current

# Import only complexity issues
grep "complexity" validation.toon > complexity.toon
planfile ticket import --from complexity.toon --source vallm --sprint backlog
```

### Score-based Importing
Import issues based on quality score:

```bash
# Import only files with score < 0.9
awk '$2 < 0.9 {print}' validation.toon > low-score.toon
planfile ticket import --from low-score.toon --source vallm --sprint current
```

### Multiple Directories
Validate multiple projects:

```bash
for project in project1 project2 project3; do
    cd $project
    vallm . --recursive > ../validation-$project.toon
    cd ../planfile
    planfile ticket import --from ../validation-$project.toon --source vallm --sprint backlog
done
```

## Integration with Other Tools

### With code2llm
Use both tools for comprehensive analysis:

```bash
# Run both analyses
code2llm . -f toon,evolution
vallm batch . --recursive

# Import both
planfile ticket import --from evolution.toon --source code2llm --sprint backlog
planfile ticket import --from validation.toon --source vallm --sprint current
```

### With GitHub Issues
Sync validation tickets to GitHub:

```bash
# Import validation errors
planfile ticket import --from validation.toon --source vallm --sprint current

# Sync to GitHub
planfile sync github
```

## Troubleshooting

### No errors imported
- Check that validation.toon has an ERRORS[] section
- Verify error format matches expected pattern
- Ensure planfile is initialized

### Too many tickets
- Use filtering to import only critical issues
- Set a minimum score threshold
- Group similar issues

### Duplicate tickets
- Clear old validation tickets before importing
- Use unique identifiers in error messages
- Check for existing tickets

### Score not improving
- Focus on high-impact fixes first
- Check for recurring issues
- Update validation rules to prevent regressions

## Metrics Dashboard

Create a quality dashboard:

```bash
# Generate quality report
planfile stats --source vallm > quality-report.md

# Track over time
git log --oneline --grep="validation" | tail -10
```

Example report sections:
- Current validation score
- Top issue types
- Files with most issues
- Trend over time
- Critical issues count

## Related Examples

- `../code2llm/` - Import refactoring tasks as tickets
- `../github/` - Sync tickets with GitHub Issues
- `../multi-ticket/` - Route tickets to multiple systems
