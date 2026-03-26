# Planfile CLI Reference

Complete command-line interface documentation for Planfile.

## Installation

```bash
pip install planfile[all]
```

## Global Options

```bash
planfile [OPTIONS] COMMAND [ARGS]...

Options:
  --version     Show version and exit
  --help        Show this message and exit
  --verbose     Enable verbose output
  --quiet       Suppress output
  --config PATH Path to config file
  --log-level   Logging level (DEBUG|INFO|WARNING|ERROR)
```

## Commands

### Auto Commands

#### auto loop
Run automated CI/CD bug-fix loop.

```bash
planfile auto loop [OPTIONS]

Options:
  --strategy PATH        Strategy file path [required]
  --project PATH         Project directory [default: .]
  --backend TEXT         Backend(s) to use [default: github]
  --max-iterations INT   Maximum iterations [default: 5]
  --auto-fix            Enable auto-fix [default: False]
  --dry-run             Preview mode [default: False]
  --output PATH          Results file [default: results.json]
  --format TEXT         Output format [json|yaml|table]
  --continue-on-error    Continue on errors [default: False]
```

Examples:
```bash
# Basic auto-loop
planfile auto loop --strategy planfile.yaml

# With multiple backends
planfile auto loop --strategy strategy.yaml --backend github --backend jira

# With auto-fix enabled
planfile auto loop --strategy strategy.yaml --auto-fix --max-iterations 10

# Dry run to preview
planfile auto loop --strategy strategy.yaml --dry-run --verbose

# Save results to file
planfile auto loop --strategy strategy.yaml --output results.json --format yaml
```

#### auto ci-status
Check CI/CD status and progress.

```bash
planfile auto ci-status [OPTIONS]

Options:
  --project PATH     Project directory [default: .]
  --format TEXT      Output format [table|json|yaml]
  --detailed         Show detailed information
  --since TEXT       Show status since timestamp
```

Examples:
```bash
# Check current status
planfile auto ci-status

# Detailed status
planfile auto ci-status --detailed --format json

# Status since yesterday
planfile auto ci-status --since "2024-01-01"
```

#### auto stop
Stop running auto-loop processes.

```bash
planfile auto stop [OPTIONS]

Options:
  --force        Force stop all processes
  --pid INT      Stop specific process ID
```

Examples:
```bash
# Stop all processes
planfile auto stop

# Force stop
planfile auto stop --force

# Stop specific process
planfile auto stop --pid 12345
```

### Strategy Commands

#### strategy apply
Apply strategy to create/update tickets.

```bash
planfile strategy apply [OPTIONS]

Options:
  --strategy PATH      Strategy file path [required]
  --project PATH       Project directory [default: .]
  --backend TEXT       Backend to use [required]
  --dry-run           Preview mode [default: False]
  --force             Force overwrite existing tickets
  --filter TEXT       Filter tasks by type/priority
  --output PATH       Save results to file
```

Examples:
```bash
# Apply strategy
planfile strategy apply --strategy strategy.yaml --backend github

# Dry run to preview
planfile strategy apply --strategy strategy.yaml --backend jira --dry-run

# Filter by task type
planfile strategy apply --strategy strategy.yaml --backend github --filter "type=bug"

# Force update existing tickets
planfile strategy apply --strategy strategy.yaml --backend github --force
```

#### strategy review
Review strategy execution progress.

```bash
planfile strategy review [OPTIONS]

Options:
  --strategy PATH      Strategy file path [required]
  --project PATH       Project directory [default: .]
  --backend TEXT       Backend to use [required]
  --format TEXT        Output format [table|markdown|json]
  --output PATH        Save report to file
  --detailed          Include detailed metrics
  --since TEXT         Review since timestamp
```

Examples:
```bash
# Review progress
planfile strategy review --strategy strategy.yaml --backend github

# Generate markdown report
planfile strategy review --strategy strategy.yaml --backend github --format markdown --output report.md

# Detailed review
planfile strategy review --strategy strategy.yaml --backend github --detailed

# Review since last week
planfile strategy review --strategy strategy.yaml --backend github --since "2024-01-01"
```

#### strategy validate
Validate strategy file against schema.

```bash
planfile strategy validate [OPTIONS]

Options:
  --strategy PATH      Strategy file path [required]
  --schema TEXT        Schema validation level [strict|lenient|none]
  --format TEXT        Output format [table|json]
  --fix               Attempt to fix validation errors
```

Examples:
```bash
# Validate with strict schema
planfile strategy validate --strategy strategy.yaml --schema strict

# Lenient validation
planfile strategy validate --strategy strategy.yaml --schema lenient

# Fix validation errors
planfile strategy validate --strategy strategy.yaml --fix
```

#### strategy export
Export strategy to different formats.

```bash
planfile strategy export [OPTIONS]

Options:
  --strategy PATH      Strategy file path [required]
  --format TEXT        Export format [json|yaml|markdown|csv]
  --output PATH        Output file path
  --template PATH      Use custom template
  --include-metrics   Include execution metrics
```

Examples:
```bash
# Export to JSON
planfile strategy export --strategy strategy.yaml --format json --output strategy.json

# Export to Markdown
planfile strategy export --strategy strategy.yaml --format markdown --output strategy.md

# Export with metrics
planfile strategy export --strategy strategy.yaml --format json --include-metrics
```

### Backend Commands

#### backend test
Test backend connection and permissions.

```bash
planfile backend test [OPTIONS] BACKEND

Options:
  --verbose           Show detailed test results
  --permissions       Check permissions
  --timeout INT       Connection timeout [default: 30]
```

Examples:
```bash
# Test GitHub connection
planfile backend test github

# Test with permissions check
planfile backend test jira --permissions --verbose

# Test with custom timeout
planfile backend test gitlab --timeout 60
```

#### backend list
List available backends and their status.

```bash
planfile backend list [OPTIONS]

Options:
  --status         Show connection status
  --configured     Show only configured backends
  --format TEXT    Output format [table|json]
```

Examples:
```bash
# List all backends
planfile backend list

# Show connection status
planfile backend list --status

# Show only configured backends
planfile backend list --configured --format json
```

#### backend configure
Configure backend settings.

```bash
planfile backend configure [OPTIONS] BACKEND

Options:
  --interactive     Interactive configuration
  --token TEXT      Set authentication token
  --url TEXT        Set API URL
  --project TEXT    Set project name/ID
  --save           Save configuration to file
```

Examples:
```bash
# Interactive configuration
planfile backend configure github --interactive

# Set token directly
planfile backend configure jira --token ATATT3xFfGF0

# Configure and save
planfile backend configure gitlab --url https://gitlab.com --save
```

### Config Commands

#### config show
Show current configuration.

```bash
planfile config show [OPTIONS]

Options:
  --section TEXT     Show specific section
  --format TEXT      Output format [table|json|yaml]
  --mask-secrets     Mask sensitive values [default: True]
```

Examples:
```bash
# Show all configuration
planfile config show

# Show specific section
planfile config show --section backends

# Show without masking secrets
planfile config show --mask-secrets false
```

#### config set
Set configuration value.

```bash
planfile config set [OPTIONS] KEY VALUE

Options:
  --global          Set global configuration
  --local           Set local configuration
  --type TEXT       Value type [string|int|bool|list]
```

Examples:
```bash
# Set default backend
planfile config set default_backend github

# Set global configuration
planfile config set --global auto_fix true

# Set list value
planfile config set backends github,jira --type list
```

#### config reset
Reset configuration to defaults.

```bash
planfile config reset [OPTIONS]

Options:
  --section TEXT     Reset specific section
  --global          Reset global configuration
  --local           Reset local configuration
  --force           Force reset without confirmation
```

Examples:
```bash
# Reset all configuration
planfile config reset --force

# Reset specific section
planfile config reset --section backends

# Reset global configuration
planfile config reset --global
```

### AI Commands

#### ai test
Test AI service connection.

```bash
planfile ai test [OPTIONS]

Options:
  --provider TEXT    AI provider [openai|anthropic|local]
  --model TEXT       Specific model to test
  --prompt TEXT      Test prompt
  --timeout INT      Request timeout [default: 30]
```

Examples:
```bash
# Test OpenAI
planfile ai test --provider openai

# Test specific model
planfile ai test --provider openai --model gpt-4

# Test with custom prompt
planfile ai test --provider openai --prompt "Summarize this bug report"
```

#### ai analyze
Analyze text with AI.

```bash
planfile ai analyze [OPTIONS] INPUT

Options:
  --provider TEXT     AI provider [default: openai]
  --model TEXT        Specific model
  --type TEXT         Analysis type [bug|code|strategy]
  --output PATH       Save analysis to file
  --format TEXT       Output format [text|json|yaml]
```

Examples:
```bash
# Analyze bug report
planfile ai analyze --type bug bug_report.txt

# Analyze with specific provider
planfile ai analyze --provider anthropic --model claude-3 code_issue.py

# Save analysis
planfile ai analyze --type strategy strategy.yaml --output analysis.json
```

### Init Commands

#### init project
Initialize new Planfile project.

```bash
planfile init project [OPTIONS] [NAME]

Options:
  --path PATH         Project directory [default: .]
  --template TEXT    Project template [web|mobile|api|library]
  --backend TEXT      Default backend
  --force            Force overwrite existing files
```

Examples:
```bash
# Initialize web project
planfile init project my-web-app --template web

# Initialize with specific backend
planfile init project my-api --template api --backend github

# Force initialize
planfile init project . --template mobile --force
```

#### init strategy
Create new strategy file.

```bash
planfile init strategy [OPTIONS] [NAME]

Options:
  --output PATH       Output file path
  --template TEXT     Strategy template [basic|advanced|custom]
  --project-type TEXT Project type [web|mobile|api|library]
  --domain TEXT       Project domain
  --interactive       Interactive mode
```

Examples:
```bash
# Create basic strategy
planfile init strategy my-strategy --template basic

# Create with interactive mode
planfile init strategy --interactive

# Create for specific project type
planfile init strategy --template advanced --project-type web --domain fintech
```

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Validation error
- `3`: Configuration error
- `4`: Backend connection error
- `5`: Strategy error
- `130`: Interrupted (Ctrl+C)

## Configuration Files

### Global Config
```yaml
# ~/.planfile/config.yaml
default_backend: github
auto_fix: false
max_iterations: 5
log_level: INFO

backends:
  github:
    token: ${GITHUB_TOKEN}
  jira:
    url: ${JIRA_URL}
    email: ${JIRA_EMAIL}
    token: ${JIRA_TOKEN}

ai:
  provider: openai
  model: gpt-4
  temperature: 0.1
```

### Project Config
```yaml
# .planfile/config.yaml
strategy: strategy.yaml
backends: [github, jira]
quality_gates:
  - test_coverage: 80
  - security_scan: true
```

## Environment Variables

```bash
# Planfile
PLANFILE_CONFIG_PATH    # Path to config file
PLANFILE_LOG_LEVEL      # Logging level
PLANFILE_DEBUG         # Enable debug mode

# Backend-specific
GITHUB_TOKEN           # GitHub personal access token
GITHUB_REPO            # GitHub repository (owner/repo)
JIRA_URL              # Jira instance URL
JIRA_EMAIL            # Jira user email
JIRA_TOKEN            # Jira API token
JIRA_PROJECT          # Jira project key
GITLAB_TOKEN          # GitLab personal access token
GITLAB_PROJECT_ID     # GitLab project ID

# AI Services
OPENAI_API_KEY        # OpenAI API key
ANTHROPIC_API_KEY     # Anthropic API key
```

## Examples

### Complete Workflow
```bash
# 1. Initialize project
planfile init project my-app --template web --backend github

# 2. Create strategy
planfile init strategy my-strategy --interactive

# 3. Validate strategy
planfile strategy validate --strategy my-strategy.yaml

# 4. Test backend connection
planfile backend test github --permissions

# 5. Apply strategy (dry run)
planfile strategy apply --strategy my-strategy.yaml --backend github --dry-run

# 6. Run auto-loop
planfile auto loop --strategy my-strategy.yaml --backend github --max-iterations 3

# 7. Review progress
planfile strategy review --strategy my-strategy.yaml --backend github --format markdown --output progress.md

# 8. Check CI status
planfile auto ci-status --detailed
```

### Advanced Usage
```bash
# Multi-backend setup
planfile auto loop \
  --strategy strategy.yaml \
  --backend github \
  --backend jira \
  --auto-fix \
  --max-iterations 10 \
  --output results.json

# Custom configuration
planfile config set default_backend github --global
planfile config set auto_fix true --global
planfile config set max_iterations 5 --global

# Batch operations
for backend in github jira gitlab; do
  planfile backend test $backend --permissions
done

# Scheduled execution
echo "0 9 * * 1 cd /app && planfile auto loop --strategy strategy.yaml --backend github" | crontab -
```

---

**Planfile CLI** - Powerful command-line control over your SDLC automation. 🚀
