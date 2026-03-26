# CLI Commands Examples

Shows how to use all new CLI commands in planfile. This example demonstrates the command-line interface for various operations.

## Commands Demonstrated

- `planfile template` - Generate project templates
- `planfile stats` - View strategy statistics
- `planfile export` - Export to various formats
- `planfile compare` - Compare two strategies
- `planfile validate` - Validate strategy files
- `planfile health` - Check project health
- `planfile generate-from-files` - Generate from file analysis

## Files

- `cli_command_examples.py` - Main example script
- `run.sh` - Convenience script to run the example

## Running

```bash
# Using the convenience script
./run.sh

# Or directly with Python
python3 cli_command_examples.py
```

## Command Examples

### 1. Generate Templates
```bash
planfile template web ecommerce --output web-template.yaml
planfile template mobile healthcare --output mobile-template.yaml
planfile template ml finance --output ml-template.yaml
```

### 2. View Statistics
```bash
planfile stats web-template.yaml
```
Shows:
- Total sprints and tasks
- Quality gates
- Sprint breakdown
- Duration analysis

### 3. Export Formats
```bash
planfile export strategy.yaml --format yaml --output export.yaml
planfile export strategy.yaml --format json --output export.json
planfile export strategy.yaml --format html --output report.html
planfile export strategy.yaml --format csv --output tasks.csv
```

### 4. Compare Strategies
```bash
planfile compare strategy1.yaml strategy2.yaml
```
Shows:
- Similarity percentage
- Common elements
- Differences
- Unique elements

### 5. Validate Strategies
```bash
planfile validate strategy.yaml --verbose
```
Validates:
- YAML syntax
- Required fields
- Data types
- Structure integrity

### 6. Health Check
```bash
planfile health . --focus quality
```
Analyzes:
- Project structure
- Code quality
- Issues found
- Recommendations

### 7. Generate from Files
```bash
planfile generate-from-files . --focus quality --max-sprints 3
```
Generates strategy from:
- File analysis
- Issue extraction
- Metrics collection
- Sprint creation

## Generated Files

- `cli-example-*.yaml` - Generated strategies
- `cli-example-*.json` - JSON exports
- `cli-example.html` - HTML report
- `cli-generated-from-files.yaml` - File-based generation

## Tips

- All commands support `--help` for more options
- Use `--verbose` for detailed output
- Combine commands for workflows
- Export to HTML for visual reports
- Use health check regularly
