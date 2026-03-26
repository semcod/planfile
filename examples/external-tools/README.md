# External Tools Examples

Integration with external analysis tools for deeper code analysis. This example shows how to use code2llm, vallm, and redup with planfile.

## External Tools

- **code2llm** - Code complexity analysis
  - Analyzes cyclomatic complexity
  - Identifies critical functions
  - Provides complexity metrics

- **vallm** - Validation and linting
  - Validates code quality
  - Finds errors and warnings
  - Checks standards compliance

- **redup** - Code duplication detection
  - Finds duplicate code blocks
  - Calculates savings from deduplication
  - Identifies refactoring opportunities

## Files

- `external_tools_examples.py` - Main example script
- `run.sh` - Convenience script to run the example

## Prerequisites

Install external tools (optional but recommended):

```bash
pip install code2llm vallm redup
```

## Running

```bash
# Using the convenience script
./run.sh

# Or directly with Python
python3 external_tools_examples.py
```

## Examples Included

### 1. Check External Tools Availability
Verifies which external tools are installed and ready to use.

### 2. Run Individual Tools
Runs each tool separately and shows their output:
- code2llm analysis
- vallm validation
- redup duplication detection

### 3. Run All Tools
Executes all available tools and collects combined results:
- Average cyclomatic complexity
- Critical functions count
- Validation errors and warnings
- Duplication groups
- Pass rate metrics

### 4. Generate Strategy with Tools
Creates a strategy based on external tool analysis:
- Issues from high CC functions
- Tasks from validation errors
- Refactoring from duplication
- Quality gates from metrics

### 5. Custom Analysis with Focus
Demonstrates focused analysis on specific areas:
- Quality-focused strategies
- Priority-based task generation
- Custom quality gates

## Generated Files

- `analysis.toon.yaml` - code2llm output (if available)
- `validation.toon.yaml` - vallm output (if available)
- `duplication.toon.yaml` - redup output (if available)
- `external-tools-generated.yaml` - Strategy from external analysis
- `quality-focused.yaml` - Quality-focused strategy

## Output Examples

### Without External Tools
The example still works without external tools, showing:
- How to check availability
- Graceful fallback behavior
- Template-based generation

### With External Tools
When tools are available, you get:
- Real project metrics
- Issue-based task generation
- Data-driven quality gates
- Comprehensive analysis

## Tips

- External tools are optional - examples work without them
- Tools analyze the parent directory (planfile project)
- Generated strategies include real metrics from tools
- Use for continuous integration pipelines
- Combine with focus areas for targeted improvements
