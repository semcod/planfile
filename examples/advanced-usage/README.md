# Advanced Usage Examples

Advanced patterns and workflows for power users. This example demonstrates complex use cases and customizations.

## Advanced Features

- **Custom File Patterns** - Analyze specific file types
- **Focus Area Strategies** - Generate targeted strategies
- **Iterative Refinement** - Improve strategies step by step
- **Batch Processing** - Process multiple directories
- **Custom Metrics** - Add domain-specific metrics
- **CI/CD Integration** - Automated workflows

## Files

- `advanced_usage_examples.py` - Main example script
- `run.sh` - Convenience script to run the example

## Running

```bash
# Using the convenience script
./run.sh

# Or directly with Python
python3 advanced_usage_examples.py
```

## Examples Included

### 1. Custom File Patterns
Analyzes projects with custom file patterns:
```python
patterns = ["*.py", "*.js", "*.ts", "*.yaml", "*.json", "Dockerfile", "*.md"]
```
Shows how to:
- Define custom patterns
- Analyze specific file types
- Get detailed breakdowns

### 2. Focus Area Strategies
Generates strategies for different focus areas:
- Quality - Code quality and standards
- Security - Security vulnerabilities and best practices
- Performance - Performance bottlenecks and optimization
- Testing - Test coverage and quality
- Documentation - Documentation completeness

### 3. Iterative Refinement
Demonstrates strategy improvement:
- Generate initial strategy
- Load and modify programmatically
- Add custom quality gates
- Adjust sprint durations
- Compare versions

### 4. Batch Processing
Processes multiple directories:
- Analyze different project parts
- Generate individual strategies
- Create combined strategy
- Summary statistics

### 5. Custom Metrics
Adds domain-specific metrics:
- Custom issue patterns (security, performance, API)
- Metric extraction
- Custom quality gates
- Focused strategy generation

### 6. CI/CD Workflow Automation
Creates automated workflows:
- Code analysis
- Quality gate checking
- Report generation
- Task creation
- Workflow script generation

## Generated Files

### Custom Patterns
- `custom-patterns-strategy.yaml` - Strategy from custom analysis

### Focus Areas
- `focus-quality-strategy.yaml`
- `focus-security-strategy.yaml`
- `focus-performance-strategy.yaml`
- `focus-testing-strategy.yaml`
- `focus-documentation-strategy.yaml`

### Iterative Refinement
- `iterative-v1.yaml` - Initial version
- `iterative-v2.yaml` - Modified version

### Batch Processing
- `batch-core-strategy.yaml` - Core module strategy
- `batch-examples-strategy.yaml` - Examples strategy
- `batch-tests-strategy.yaml` - Tests strategy
- `batch-combined-strategy.yaml` - Combined strategy

### Custom Metrics
- `custom-metrics-strategy.yaml` - With custom metrics

### CI/CD
- `ci-analysis-strategy.yaml` - CI analysis
- `ci-workflow.sh` - Generated workflow script

## Advanced Patterns

### Custom Analysis
```python
analyzer = FileAnalyzer()
analyzer.issue_patterns['security'] = re.compile(r'SECURITY\s*[:#]?\s*(.+)')
result = analyzer.analyze_directory(path, patterns=custom_patterns)
```

### Strategy Manipulation
```python
strategy = Strategy.load("strategy.yaml")
strategy.quality_gates.append(QualityGate(...))
strategy.sprints[0].duration = "3 weeks"
```

### Batch Processing
```python
strategies = [Strategy.load(f) for f in strategy_files]
combined = strategies[0].merge(strategies[1:])
```

## Tips

- Combine examples for custom workflows
- Use custom patterns for specific domains
- Iterate on strategies for refinement
- Batch process for large projects
- Add custom metrics for domain needs
- Automate in CI/CD pipelines
