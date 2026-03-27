# Redup Integration Example

This example demonstrates how to integrate planfile with redup to turn code duplication issues into actionable refactoring tickets.

## Overview

Redup is a code duplication detection tool that identifies:
- Structural duplicates (similar code blocks)
- Similar patterns (near-duplicates)
- Refactoring opportunities
- Lines of code that can be saved

This integration shows how to:
1. Initialize a planfile project
2. Import duplication issues from redup's toon output
3. Track refactoring progress
4. Maintain code quality standards

## Files in this Example

- `duplication.toon.yaml` - Sample redup output with duplication analysis
- `run.sh` - Demonstration script showing the full pipeline
- `README.md` - This documentation

## Prerequisites

1. Install planfile:
   ```bash
   pip install -e .
   ```

2. Install redup (optional for generating new analysis):
   ```bash
   # From PyPI (if available)
   pip install redup
   
   # Or from source
   cd /home/tom/github/semcod/redup
   pip install -e .
   ```

## Running the Example

### Quick Start

```bash
cd examples/redup
./run.sh
```

This will:
- Initialize a new planfile project
- Create sample tickets
- Import duplication issues to backlog
- Show current duplication metrics

### Manual Steps

1. **Initialize planfile**:
   ```bash
   # Create planfile.yaml manually (see run.sh for structure)
   ```

2. **Create test tickets**:
   ```bash
   planfile ticket create "Test ticket" --priority normal
   ```

3. **List tickets**:
   ```bash
   planfile ticket list
   ```

4. **Import from redup**:
   ```bash
   planfile ticket import --from duplication.toon.yaml --source redup --sprint backlog
   ```

5. **Move tickets to current sprint**:
   ```bash
   planfile ticket move RD-001 --to current
   ```

## Understanding duplication.toon.yaml

The duplication.toon.yaml file contains redup analysis results:

```yaml
# redup/duplication | 3 groups | 78f 15234L | 2026-03-27

SUMMARY:
  files_scanned: 78
  total_lines:   15234
  dup_groups:    3
  dup_fragments: 7
  saved_lines:   45

DUPLICATES[3] (ranked by impact):
  [hash]   TYPE  name  L=lines N=occurrences saved=lines sim=similarity
      file:line-range  (function_name)

REFACTOR[3] (ranked by priority):
  [1] ○ refactoring_type   → target_file
      WHY: description
      FILES: list of files
```

Each duplicate includes:
- **Hash**: Unique identifier for the duplicate group
- **Type**: STRU (structural) or SIMILAR
- **Lines**: Length of duplicated block
- **Occurrences**: Number of times it appears
- **Saved**: Lines that can be recovered
- **Files**: Locations of the duplicates

## Priority Mapping

Redup issues are mapped to planfile priorities based on impact:

| Lines Saved | Priority | Description |
|-------------|----------|-------------|
| > 20        | critical | Major duplication, high impact |
| 10-20       | high     | Significant duplication |
| 5-10        | normal   | Moderate duplication |
| < 5         | low      | Minor duplication |

## Generating New Analysis

To generate a fresh duplication.toon.yaml from your code:

```bash
redup . --format toon
```

This will analyze the current directory and create a duplication.toon.yaml file.

## Quality Metrics

The example targets these quality metrics:

- **0 duplicate groups**: No code duplication
- **100% unique code**: All code is original
- **No patterns > 3 lines**: Small duplications only

## Refactoring Strategies

### 1. Extract Base Class
For structural duplicates across multiple files:

```python
# Before: Duplicated in github.py, gitlab.py, jira.py
def create_ticket(self, title, description):
    # 12 lines of similar code
    
# After: Extract to base.py
class IntegrationBackend:
    def create_ticket(self, title, description):
        # Common implementation
```

### 2. Extract Utility Function
For repeated code blocks:

```python
# Before: Duplicated in multiple files
def validate_config(self, config):
    # 8 lines of validation
    
# After: Extract to utils/config.py
def validate_integration_config(config):
    # Common validation logic
```

### 3. Create Template/Pattern
For similar but not identical code:

```python
# Use templates or builders
class TicketBuilder:
    def __init__(self, integration_type):
        self.integration_type = integration_type
    
    def build(self, **kwargs):
        # Build ticket based on type
```

## Workflow Integration

### 1. Regular Analysis
Run redup regularly to detect new duplications:

```bash
# Weekly cron job
0 9 * * 1 cd /path/to/project && redup . --format toon && planfile ticket import --from duplication.toon.yaml --source redup --sprint backlog
```

### 2. Pre-commit Check
Add to pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: redup
        name: Check for duplications
        entry: redup
        language: system
        args: [--format, toon, --max-groups, 0]
        pass_filenames: false
```

### 3. CI/CD Pipeline
Add to your CI pipeline:

```yaml
# .github/workflows/duplication.yml
name: Code Duplication Check
on: [push, pull_request]
jobs:
  check-duplication:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run redup
        run: |
          pip install redup
          redup . --format toon
      - name: Import to planfile
        run: |
          pip install planfile
          planfile ticket import --from duplication.toon.yaml --source redup --sprint backlog
      - name: Check for new duplications
        run: |
          # Fail if new duplications found
          GROUPS=$(grep "dup_groups:" duplication.toon.yaml | awk '{print $2}')
          if [ "$GROUPS" -gt 0 ]; then
            echo "Found $GROUPS duplicate groups"
            exit 1
          fi
```

## Best Practices

1. **Fix High Impact First**: Prioritize duplications that save the most lines
2. **Extract to Common Base**: Use inheritance or composition
3. **Create Utilities**: Move repeated logic to shared modules
4. **Review Before Refactoring**: Ensure duplicates are truly equivalent
5. **Test After Refactoring**: Verify functionality is preserved

## Advanced Usage

### Custom Priority Mapping
Configure custom priority rules in planfile.yaml:

```yaml
importers:
  redup:
    priority_rules:
      "saved_lines > 20": "critical"
      "saved_lines > 10": "high"
      "saved_lines > 5": "normal"
      "saved_lines <= 5": "low"
```

### Filtering Duplicates
Import only specific types of issues:

```bash
# Import only structural duplicates
awk '/STRU/' duplication.toon.yaml > structural.toon.yaml
planfile ticket import --from structural.toon.yaml --source redup --sprint backlog

# Import only high-impact
awk '/saved=[2-9][0-9]/' duplication.toon.yaml > high-impact.toon.yaml
planfile ticket import --from high-impact.toon.yaml --source redup --sprint current
```

### Multiple Directories
Analyze multiple projects:

```bash
for project in project1 project2 project3; do
    cd $project
    redup . --format toon > ../duplication-$project.toon.yaml
    cd ../planfile
    planfile ticket import --from ../duplication-$project.toon.yaml --source redup --sprint backlog
done
```

## Integration with Other Tools

### With code2llm
Use both tools for comprehensive analysis:

```bash
# Run both analyses
code2llm . -f toon,evolution
redup . --format toon

# Import both
planfile ticket import --from evolution.toon --source code2llm --sprint backlog
planfile ticket import --from duplication.toon.yaml --source redup --sprint backlog
```

### With vallm
Combine validation and duplication fixes:

```bash
# Fix duplication first (reduces total code)
planfile ticket import --from duplication.toon.yaml --source redup --sprint current

# Then validate remaining code
vallm batch . --recursive
planfile ticket import --from validation.toon.yaml --source vallm --sprint current
```

## Troubleshooting

### No duplications imported
- Check that duplication.toon.yaml has a DUPLICATES[] section
- Verify file format matches expected pattern
- Ensure planfile is initialized

### Too many tickets
- Set a minimum lines saved threshold
- Filter by similarity score
- Focus on structural duplicates first

### False positives
- Review duplicate groups manually
- Adjust similarity threshold in redup
- Exclude test files from analysis

### Duplicates reappear
- Check for copy-paste during development
- Add pre-commit hooks to prevent
- Review refactoring approach

## Metrics Dashboard

Create a duplication dashboard:

```bash
# Generate duplication report
planfile stats --source redup > duplication-report.md

# Track over time
git log --oneline --grep="duplication" | tail -10
```

Example report sections:
- Current duplicate groups
- Lines of code saved
- Top duplicated patterns
- Refactoring progress
- Trend over time

## Related Examples

- `../code2llm/` - Import refactoring tasks as tickets
- `../vallm/` - Import validation errors as tickets
- `../github/` - Sync tickets with GitHub Issues
- `../multi-ticket/` - Route tickets to multiple systems
