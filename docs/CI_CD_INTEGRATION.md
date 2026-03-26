# Planfile CI/CD Integration

Complete automation for bug-fix loop: tests → tickets → fixes → retests.

## Overview

Planfile provides automated CI/CD integration that:
- Runs tests and code analysis
- Generates bug reports using LLM when tests fail
- Creates tickets in PM systems (GitHub, Jira, GitLab)
- Optionally auto-fixes bugs with LLM
- Repeats until all tests pass or strategy is complete

## Quick Start

### 1. Install

```bash
pip install planfile[all]
pip install llx  # For AI analysis
```

### 2. Configure Environment

```bash
# GitHub
export GITHUB_TOKEN=your_token
export GITHUB_REPO=owner/repo

# Jira
export JIRA_URL=https://company.atlassian.net
export JIRA_EMAIL=your@email.com
export JIRA_TOKEN=your_token
export JIRA_PROJECT=PROJ

# GitLab
export GITLAB_TOKEN=your_token
export GITLAB_PROJECT_ID=123

# AI Services (optional)
export OPENAI_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key
```

### 3. Run Auto-Loop

```bash
planfile auto loop \
  --strategy ./strategy.yaml \
  --project . \
  --backend github \
  --backend jira \
  --max-iterations 5 \
  --auto-fix
```

## 🔄 Auto-Loop Process

### Phase 1: Test Execution
```bash
# Run your test suite
pytest tests/ -v --cov=src

# Code quality checks
ruff check src/
mypy src/
```

### Phase 2: Bug Detection
- Identify failing tests
- Analyze code quality issues
- Check security vulnerabilities
- Detect performance regressions

### Phase 3: AI Analysis
```python
# Generate bug report
bug_report = llx.analyze_failure(
    test_output=test_results,
    code_context=source_code,
    error_type="test_failure"
)
```

### Phase 4: Ticket Creation
```yaml
# GitHub Issue
title: "Fix: Authentication module test failures"
body: |
  ## Bug Report
  **Test**: `test_auth_login_invalid_credentials`
  **Error**: `AssertionError: Expected 401, got 500`
  
  ## Root Cause
  The authentication service is not properly handling invalid credentials,
  causing a server error instead of returning 401 Unauthorized.
  
  ## Suggested Fix
  Update the `auth_service.py` to catch validation errors and return
  appropriate HTTP status codes.
  
  ## Files Affected
  - `src/auth/auth_service.py`
  - `tests/test_auth.py`
```

### Phase 5: Auto-Fix (Optional)
```python
# Generate fix code
fix_code = llx.generate_fix(
    bug_report=bug_report,
    source_code=auth_service_code,
    context="authentication_error_handling"
)

# Apply fix
apply_fix(fix_code, file_path="src/auth/auth_service.py")
```

### Phase 6: Verification
```bash
# Re-run tests
pytest tests/test_auth.py -v

# Verify fix
if tests_pass:
    close_ticket(ticket_id)
else:
    update_ticket_status(ticket_id, "needs_review")
```

## 🐳 Docker Integration

### Dockerfile
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Planfile
RUN pip install planfile[all]

# Copy project
WORKDIR /workspace
COPY . .

# Run auto-loop
CMD ["planfile", "auto", "loop", "--strategy", "strategy.yaml"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  planfile-runner:
    build: .
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_REPO=${GITHUB_REPO}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - .:/workspace
      - ./results:/app/results
    command: planfile auto loop --strategy strategy.yaml --max-iterations 10
```

## 🔧 Configuration

### Strategy Configuration
```yaml
name: "CI/CD Automation Strategy"
project_type: "web"
domain: "software"

sprints:
  - id: 1
    name: "Bug Fix Sprint"
    length_days: 7
    quality_gates:
      - type: "test_coverage"
        threshold: 80
      - type: "security_scan"
        threshold: "no_critical"
    tasks:
      - type: "bug_fix"
        pattern: "test_failure"
        auto_fix: true
        priority: "high"
```

### Quality Gates
```yaml
quality_gates:
  - name: "Test Coverage"
    type: "coverage"
    threshold: 80
    command: "pytest --cov=src --cov-report=xml"
    
  - name: "Security Scan"
    type: "security"
    threshold: "no_critical"
    command: "bandit -r src/"
    
  - name: "Code Quality"
    type: "quality"
    threshold: "no_issues"
    command: "ruff check src/"
```

## 🚀 GitHub Actions

### Workflow Configuration
```yaml
name: Planfile Auto-Loop

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  auto-loop:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install Planfile
        run: pip install planfile[all]
        
      - name: Run Auto-Loop
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          planfile auto loop \
            --strategy .github/strategy.yaml \
            --project . \
            --backend github \
            --max-iterations 3 \
            --auto-fix
```

## 📊 Monitoring and Reporting

### Progress Tracking
```bash
# Check CI status
planfile auto ci-status

# View detailed results
planfile auto results --format json

# Generate report
planfile strategy report \
  --strategy strategy.yaml \
  --output ci-report.md
```

### Metrics Collection
```yaml
metrics:
  - name: "bug_fix_rate"
    type: "percentage"
    target: 95
    
  - name: "test_coverage"
    type: "percentage"
    target: 80
    
  - name: "auto_fix_success"
    type: "percentage"
    target: 70
```

## 🔄 Integration Examples

### GitHub Integration
```python
from strategy.integrations.github import GitHubBackend

github = GitHubBackend(
    token="github_token",
    repo="owner/repo"
)

# Create issue for bug
issue = github.create_issue(
    title="Fix: Authentication test failure",
    body=bug_report,
    labels=["bug", "auto-generated"]
)

# Update issue status
github.update_issue(issue.id, state="closed")
```

### Jira Integration
```python
from strategy.integrations.jira import JiraBackend

jira = JiraBackend(
    url="https://company.atlassian.net",
    email="user@company.com",
    token="jira_token",
    project="PROJ"
)

# Create ticket
ticket = jira.create_ticket(
    summary="Authentication module bug fix",
    description=bug_report,
    issue_type="Bug",
    priority="High"
)
```

### GitLab Integration
```python
from strategy.integrations.gitlab import GitLabBackend

gitlab = GitLabBackend(
    token="gitlab_token",
    project_id=123
)

# Create issue
issue = gitlab.create_issue(
    title="Fix authentication bug",
    description=bug_report,
    labels=["bug", "auto-generated"]
)
```

## 🛠️ Advanced Features

### Custom Test Runners
```python
from strategy.ci_runner import CustomTestRunner

class CustomRunner(CustomTestRunner):
    def run_tests(self):
        # Custom test logic
        results = subprocess.run([
            "pytest", "tests/", 
            "--cov=src", 
            "--junitxml=results.xml"
        ])
        return results.returncode == 0
```

### Custom Bug Analyzers
```python
from strategy.ci_runner import BugAnalyzer

class CustomAnalyzer(BugAnalyzer):
    def analyze_failure(self, test_output, code_context):
        # Custom analysis logic
        return {
            "type": "logic_error",
            "severity": "high",
            "suggested_fix": "Update validation logic"
        }
```

### Custom Ticket Templates
```yaml
ticket_templates:
  bug_fix:
    title: "Fix: {test_name} failure"
    body: |
      ## Bug Report
      **Test**: {test_name}
      **Error**: {error_message}
      
      ## Analysis
      {analysis}
      
      ## Suggested Fix
      {suggested_fix}
    labels: ["bug", "auto-generated"]
    priority: "high"
```

## 📈 Best Practices

### 1. Strategy Design
- Keep sprints focused and time-boxed
- Define clear quality gates
- Use task patterns for consistency

### 2. Test Organization
- Structure tests by feature/module
- Use descriptive test names
- Include assertion messages

### 3. Error Handling
- Provide meaningful error messages
- Include context in bug reports
- Use structured logging

### 4. AI Integration
- Provide clear prompts for LLM
- Validate AI-generated fixes
- Use human-in-the-loop for critical changes

### 5. Monitoring
- Track key metrics
- Set up alerts for failures
- Regular strategy reviews

## 🔍 Troubleshooting

### Common Issues

#### Auto-Loop Stuck
```bash
# Check current status
planfile auto ci-status

# Force stop
planfile auto stop

# Resume with different parameters
planfile auto loop --max-iterations 1 --dry-run
```

#### AI Service Issues
```bash
# Check API keys
echo $OPENAI_API_KEY

# Test AI connection
planfile ai test --provider openai

# Fallback to manual mode
planfile auto loop --no-auto-fix
```

#### Backend Connection Issues
```bash
# Test GitHub connection
planfile backend test github

# Test Jira connection
planfile backend test jira

# Check permissions
planfile backend check github --permissions
```

### Debug Mode
```bash
# Enable debug logging
planfile auto loop --debug --log-level debug

# Save detailed logs
planfile auto loop --log-file debug.log

# Dry run mode
planfile auto loop --dry-run --verbose
```

## 📚 Additional Resources

- [Planfile CLI Reference](CLI.md)
- [Strategy Schema Guide](STRATEGY_SCHEMA.md)
- [Integration Examples](EXAMPLES.md)
- [API Documentation](API.md)

---

**Planfile** - Automating your SDLC, one loop at a time. 🚀
