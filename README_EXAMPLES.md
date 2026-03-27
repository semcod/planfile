# Planfile Examples - Quick Start Guide

## 🚀 One-Command Execution

Run all examples with a single command:

```bash
./run_examples.sh
```

## 📋 Available Commands

### Basic Usage
```bash
# Run all examples
./run_examples.sh

# Run specific example
./run_examples.sh quick-start
./run_examples.sh cli-commands

# List all available examples
./run_examples.sh --list

# Check prerequisites only
./run_examples.sh --check

# Setup environment only
./run_examples.sh --setup

# Show help
./run_examples.sh --help
```

## 🎯 Available Examples

### ⚡ Quick Start
Perfect for beginners - get started with planfile in minutes!
```bash
./run_examples.sh quick-start
```
**What you'll learn:**
- Generate strategies from project files
- Create project templates
- View strategy statistics
- Export to different formats (JSON, HTML, CSV)
- Compare strategies

### 💻 CLI Commands
Master the command-line interface:
```bash
./run_examples.sh cli-commands
```
**What you'll learn:**
- Validate strategy configurations
- Review project settings
- Apply strategies (dry run)
- View detailed statistics
- Export strategies

### 🚀 Integrated Functionality
Comprehensive demo of all features:
```bash
./run_examples.sh integrated-functionality
```
**What you'll learn:**
- File analysis without external scripts
- Template generation for different project types
- Strategy comparison and merging
- Multiple export formats
- Health checking

### 🔧 External Tools
Integration with code analysis tools:
```bash
./run_examples.sh external-tools
```
**What you'll learn:**
- code2llm - Code complexity analysis
- vallm - Validation and linting
- redup - Code duplication detection
- Combined analysis workflows

### 🎯 Advanced Usage
Power user features and patterns:
```bash
./run_examples.sh advanced-usage
```
**What you'll learn:**
- Custom file patterns
- Focus-specific strategies
- Iterative strategy refinement
- Batch processing
- CI/CD workflow automation

## 🛠️ Prerequisites

The runner automatically checks and installs dependencies:

- **Python 3.10+** - Required
- **planfile package** - Auto-installed if missing
- **expect** - Optional (for interactive tests)

### Optional Integrations

For full functionality, install optional dependencies:

```bash
# Install all integrations
pip install planfile[all]

# Or install individually
pip install PyGithub      # GitHub integration
pip install jira          # Jira integration
pip install python-gitlab # GitLab integration
pip install litellm       # LLM integration
pip install llx           # Code analysis
pip install code2llm      # External tool
pip install vallm         # External tool
pip install redup         # External tool
```

## 📁 Generated Files

Each example creates its own set of files:

**quick-start/**
- `quick-start.yaml` - Generated strategy
- `web-template.yaml` - Web project template
- `web-template.json` - JSON export

**cli-commands/**
- `test-strategy.yaml` - Test strategy
- `test-strategy.json` - JSON export

**integrated-functionality/**
- `generated-from-examples.yaml` - Strategy from analysis
- `template-*.yaml` - Various project templates
- `strategy-export.*` - Multiple export formats

## 🔧 Troubleshooting

### Common Issues

1. **"planfile command not found"**
   ```bash
   pip install -e .
   ```

2. **"Generation failed"**
   - The runner automatically falls back to template generation
   - Check if project directory exists and is accessible

3. **"Backend initialization failed"**
   - Install required backend: `pip install PyGithub`
   - Or use `--dry-run` flag to skip backend operations

4. **Permission errors**
   ```bash
   chmod +x run_examples.sh
   ```

### Environment Variables

Set these for enhanced functionality:

```bash
# GitHub integration
export GITHUB_TOKEN=your_github_token

# OpenAI integration
export OPENAI_API_KEY=your_openai_key

# OpenRouter (free LLM validation)
export OPENROUTER_API_KEY=your_openrouter_key
```

## 📊 Example Output

Each example provides colored output with:
- ✅ Success indicators
- ❌ Error messages
- ℹ️ Informational notes
- ➡️ Step indicators
- 🎯 Section headers

## 🎉 Next Steps

After running examples:

1. **Explore generated files** - Check the `.yaml` and `.json` files
2. **Try your own project** - `planfile generate-from-files /path/to/your/project`
3. **Create custom templates** - `planfile template web your-domain`
4. **Integrate with CI/CD** - Check the advanced usage examples

## 📚 More Documentation

- **Main README**: [README.md](README.md)
- **Examples Details**: [examples/README.md](examples/README.md)
- **API Documentation**: Check the `docs/` directory

---

**Tip**: Start with `./run_examples.sh quick-start` then explore other examples based on your needs!
