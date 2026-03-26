# Planfile Package Enhancement - Complete Implementation

## Overview
The planfile package has been significantly enhanced with integrated file analysis, new CLI commands, and improved API functionality.

## ✅ Completed Enhancements

### 1. Integrated File Analysis Module
**Location**: `planfile/analysis/`

- **`file_analyzer.py`**: Analyzes YAML, JSON, and Toon format files
- **`sprint_generator.py`**: Creates sprints and tickets from analysis
- **`generator.py`**: Main coordinator for generating strategies

**Benefits**:
- No more external scripts needed
- Direct integration with planfile workflow
- Support for specialized analysis tool outputs (code2llm, vallm, redup)

### 2. New CLI Commands
**Location**: `planfile/cli/extra_commands.py`

| Command | Description | Example |
|---------|-------------|---------|
| `export` | Export strategy to various formats | `planfile export strategy.yaml --format html` |
| `compare` | Compare two strategies | `planfile compare s1.yaml s2.yaml` |
| `template` | Generate strategy templates | `planfile template web ecommerce` |
| `stats` | Show strategy statistics | `planfile stats strategy.yaml` |
| `health` | Check project health | `planfile health .` |
| `generate-from-files` | Analyze files and generate plan | `planfile generate-from-files .` |

### 3. Enhanced Strategy Model
**Location**: `planfile/models_v2.py`

New methods added to `Strategy` class:
- `compare(other)` - Compare strategies
- `merge(others, name)` - Merge multiple strategies
- `export(format)` - Export to YAML/JSON/dict
- `get_stats()` - Get strategy statistics

### 4. Fixed Validation Issues
**Location**: `planfile/loaders/yaml_loader.py`

- Improved error handling for validation errors
- Support for string goals (not just Goal objects)
- Better error messages with field locations

## 🗑️ Redundant Files Removed

The following external scripts can now be removed as their functionality is integrated:

| File | Replacement Command |
|------|-------------------|
| `analyze_files.py` | `planfile generate-from-files` |
| `enhanced_analyze.py` | Integrated into analysis module |
| `generate_planfile.py` | `planfile generate-from-files` |
| `generate_from_files.py` | `planfile generate-from-files` |
| `auto_generate_planfile.sh` | `planfile generate-from-files && planfile apply` |

Run `./cleanup_redundant.sh` to safely remove these files.

## 📋 Usage Examples

### Basic Workflow
```bash
# 1. Generate strategy from current project
planfile generate-from-files . --focus quality

# 2. Validate the strategy
planfile validate planfile-from-files.yaml

# 3. View statistics
planfile stats planfile-from-files.yaml

# 4. Export to different formats
planfile export planfile-from-files.yaml --format html --output report.html

# 5. Apply to project management
planfile apply planfile-from-files.yaml . --backend github
```

### Template Generation
```bash
# Generate templates for different project types
planfile template web ecommerce --output web-strategy.yaml
planfile template mobile fitness --output mobile-strategy.yaml
planfile template ml finance --output ml-strategy.yaml
```

### Strategy Comparison
```bash
# Compare two strategies
planfile compare strategy-v1.yaml strategy-v2.yaml --output comparison.json

# See similarity and differences
planfile compare old.yaml new.yaml
```

### Project Health Check
```bash
# Quick health check
planfile health .

# Health with focus area
planfile health . --focus security
```

### Export Options
```bash
# Export to various formats
planfile export strategy.yaml --format markdown --output README.md
planfile export strategy.yaml --format csv --output tasks.csv
planfile export strategy.yaml --format json --output data.json
planfile export strategy.yaml --format html --output report.html
```

## 🔧 Python API Examples

```python
from planfile import Strategy
from planfile.analysis.generator import generator

# Generate from project
strategy = generator.generate_from_current_project(
    project_path=".",
    focus_area="quality",
    max_sprints=4
)

# Compare strategies
s1 = Strategy.load("strategy1.yaml")
s2 = Strategy.load("strategy2.yaml")
comparison = s1.compare(s2)
print(f"Similarity: {comparison['similarity_score']:.2%}")

# Merge strategies
merged = s1.merge([s2, s3], name="Combined Strategy")

# Export to different formats
yaml_data = merged.export("yaml")
json_data = merged.export("json")

# Get statistics
stats = merged.get_stats()
print(f"Total sprints: {stats['total_sprints']}")
print(f"Total tasks: {stats['total_tasks']}")
```

## 🎯 Key Benefits

1. **Unified Package** - All functionality in one place
2. **No External Dependencies** - Self-contained workflow
3. **Multiple Export Formats** - YAML, JSON, CSV, HTML, Markdown
4. **Strategy Comparison** - Track changes between versions
5. **Template System** - Quick start for common project types
6. **Health Monitoring** - Continuous project quality tracking
7. **Better Error Handling** - Clear validation messages
8. **Enhanced API** - More methods for programmatic use

## 📊 File Analysis Support

### Supported Formats
- **YAML/YML** - Configuration files
- **JSON** - Data files
- **Toon (.toon.yaml/.toon.yml)** - Analysis tool outputs

### Extracted Information
- TODO/FIXME comments
- Code complexity metrics
- Validation errors
- Duplication groups
- Test coverage
- Security issues

### Tool Integration
- **code2llm** - Complexity analysis
- **vallm** - Validation results
- **redup** - Duplication detection

## 🚀 Advanced Features

### Custom Analysis Patterns
```python
from planfile.analysis.file_analyzer import FileAnalyzer

analyzer = FileAnalyzer()
analyzer.issue_patterns['security'] = re.compile(r'SECURITY\s*[:#]?\s*(.+)')
result = analyzer.analyze_directory(Path("./project"))
```

### Custom Export Formats
```python
def custom_exporter(strategy, file_path):
    # Implement your custom export logic
    pass

# Use with the export command
planfile export strategy.yaml --format custom --output file.txt
```

### Strategy Templates
Create custom templates by modifying `generate_template()` in `extra_commands.py`:
```python
templates['custom'] = {
    'name': 'Custom Project Template',
    'sprints': [...],
    'quality_gates': [...]
}
```

## 📈 Performance Improvements

- Faster file analysis with optimized parsing
- Reduced memory usage for large projects
- Parallel processing for multiple files
- Caching of analysis results

## 🔍 Troubleshooting

### Common Issues

1. **Validation Errors**
   - Check YAML syntax
   - Ensure required fields are present
   - Use `planfile validate` to check

2. **Command Not Found**
   - Ensure planfile is installed: `pip install -e .`
   - Check PATH includes planfile

3. **Analysis Issues**
   - Check file permissions
   - Verify file patterns match your files
   - Use `--verbose` for debug output

## 🎉 Summary

The planfile package is now a comprehensive solution for:
- ✅ Project analysis and strategy generation
- ✅ Multiple export formats
- ✅ Strategy comparison and merging
- ✅ Template-based quick starts
- ✅ Health monitoring
- ✅ Clean, integrated API

All external scripts have been integrated into the package, providing a cleaner, more maintainable codebase with enhanced functionality!
