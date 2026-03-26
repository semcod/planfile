# Integrated Functionality Examples

Comprehensive demo of all new integrated features in planfile. This example shows the full power of the integrated analysis and generation system.

## Features Demonstrated

- **File Analysis** - Analyze YAML, JSON, and Toon files without external scripts
- **Template Generation** - Generate templates for different project types
- **Strategy Comparison** - Compare strategies and see similarities/differences
- **Multiple Export Formats** - Export to YAML, JSON, CSV, HTML, Markdown
- **Statistics & Health** - Get detailed statistics and health checks
- **Strategy Merging** - Combine multiple strategies into one

## Files

- `integrated_functionality_examples.py` - Main example script
- `run.sh` - Convenience script to run the example

## Running

```bash
# Using the convenience script
./run.sh

# Or directly with Python
python3 integrated_functionality_examples.py
```

## Examples Included

### 1. Generate from Files
Analyzes the strategies directory and generates a complete strategy based on file analysis.

### 2. Template Generation
Creates templates for different project types:
- Web applications
- Mobile applications  
- Machine learning projects

### 3. Strategy Comparison
Compares different strategies and shows:
- Similarity score
- Common elements
- Differences
- Unique elements

### 4. Export Formats
Demonstrates exporting to:
- YAML (native format)
- JSON (for API integration)
- Dict (Python object)
- HTML (reports)
- CSV (data analysis)

### 5. Strategy Statistics
Shows detailed statistics:
- Total sprints and tasks
- Task type breakdown
- Duration analysis
- Quality gates count

### 6. Strategy Merging
Merges multiple strategies into a single comprehensive strategy.

### 7. External Tools Integration
(Optional) Shows integration with external analysis tools if available:
- code2llm - Complexity analysis
- vallm - Validation
- redup - Duplication detection

## Generated Files

- `generated-from-examples.yaml` - Strategy from file analysis
- `template-*.yaml` - Project templates
- `strategy-export.*` - Various export formats
- `merged-strategy.yaml` - Combined strategy
- `external-tools-strategy.yaml` - With external analysis (if tools available)

## Prerequisites

- Python 3.8+
- planfile package installed
- Optional: `pip install code2llm vallm redup` for external tools

## Tips

- Each example is independent - you can run them individually
- Generated files are preserved for inspection
- External tools are optional - the example works without them
- Check the generated YAML files to understand the structure
