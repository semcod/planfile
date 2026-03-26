# SprintStrat CI/CD Integration

Complete automation for bug-fix loop: tests → tickets → fixes → retests.

## Overview

SprintStrat provides automated CI/CD integration that:
- Runs tests and code analysis
- Generates bug reports using LLM when tests fail
- Creates tickets in PM systems (GitHub, Jira, GitLab)
- Optionally auto-fixes bugs with LLM
- Repeats until all tests pass or strategy is complete

## Quick Start

### 1. Install

```bash
pip install strategy-pm[all]
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
```

### 3. Run Auto-Loop

```bash
strategy-pm auto loop \
  --strategy ./strategy.yaml \
  --project . \
  --backend github \
  --backend jira \
  --max-iterations 5 \
  --auto-fix
```

## CLI Commands

### auto loop

Run the complete CI/CD loop:

```bash
strategy-pm auto loop [OPTIONS] STRATEGY_PATH PROJECT_PATH
```

Options:
- `--backend, -b`: PM backends (github, jira, gitlab)
- `--max-iterations, -m`: Max iterations (default: 10)
- `--auto-fix, -a`: Enable LLM auto-fix
- `--output, -o`: Save results to file
- `--dry-run, -d`: Simulate without creating tickets

Example:
```bash
strategy-pm auto loop \
  --strategy strategy.yaml \
  --project . \
  --backend github \
  --max-iterations 3 \
  --auto-fix \
  --output results.json
```

### auto ci-status

Check current CI status:

```bash
strategy-pm auto ci-status --project .
```

## CI/CD Platform Integration

### GitHub Actions

Create `.github/workflows/ci-auto-loop.yml`:

```yaml
name: CI/CD with Auto Bug-Fix Loop

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci-loop:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
      pull-requests: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install strategy-pm[github] pytest
          pip install llx
      
      - name: Run CI Auto-Loop
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPO: ${{ github.repository }}
        run: |
          strategy-pm auto loop \
            --strategy ./strategy.yaml \
            --project . \
            --backend github \
            --max-iterations 5 \
            --output ci-results.json
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - ticket
  - fix

run_tests:
  stage: test
  script:
    - pip install strategy-pm[jira] pytest
    - pytest --cov=src --cov-report=json
  artifacts:
    reports:
      junit: test-results.xml
    paths:
      - coverage.json

create_tickets:
  stage: ticket
  script:
    - strategy-pm auto loop \
        --strategy ./strategy.yaml \
        --project . \
        --backend jira \
        --max-iterations 1
  dependencies:
    - run_tests
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    environment {
        GITHUB_TOKEN = credentials('github-token')
        JIRA_TOKEN = credentials('jira-token')
    }
    
    stages {
        stage('Test') {
            steps {
                sh 'pip install strategy-pm[github,jira] pytest'
                sh 'pytest --cov=src --cov-report=json'
            }
        }
        
        stage('Auto-Loop') {
            steps {
                script {
                    sh '''
                        strategy-pm auto loop \
                            --strategy ./strategy.yaml \
                            --project . \
                            --backend github \
                            --backend jira \
                            --max-iterations 5 \
                            --output ci-results.json
                    '''
                }
            }
        }
    }
}
```

## Docker Integration

### Build Image

```bash
docker build -t sprintstrat/runner:latest .
```

### Run with Docker Compose

```bash
# Configure environment
cp .env.example .env
# Edit .env with your tokens

# Run
docker-compose up -d

# View logs
docker-compose logs -f
```

### Docker Run

```bash
docker run -e GITHUB_TOKEN=$GITHUB_TOKEN \
           -e GITHUB_REPO=owner/repo \
           -v $(pwd)/strategy.yaml:/app/strategy.yaml:ro \
           -v $(pwd)/workspace:/workspace \
           sprintstrat/runner:latest \
           strategy.yaml /workspace
```

## Configuration

### Strategy File

Your `strategy.yaml` should include:

```yaml
name: "CI/CD Strategy"
project_type: "web"
domain: "your-domain"
goal:
  short: "Automated CI/CD with bug-fix loop"
  quality:
    - "Test coverage > 80%"
    - "All tests passing"
  delivery:
    - "Tickets created for failures"
    - "Auto-fix applied when possible"

sprints:
  - id: 1
    name: "CI/CD Loop"
    objectives:
      - "Run tests"
      - "Fix failures"
      - "Maintain coverage"
    tasks: ["bug", "feature"]

tasks:
  patterns:
    - id: "bug"
      type: "bug"
      title: "Auto: {test_name} failure"
      description: |
        Test failure detected:
        - Test: {test_name}
        - Coverage: {coverage}%
        - Error: {error_message}
      priority: "high"
      model_hints:
        triage: "balanced"
        implementation: "local"
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | GitHub backend | GitHub personal access token |
| `GITHUB_REPO` | GitHub backend | Repository in format owner/repo |
| `JIRA_URL` | Jira backend | Jira instance URL |
| `JIRA_EMAIL` | Jira backend | Jira user email |
| `JIRA_TOKEN` | Jira backend | Jira API token |
| `JIRA_PROJECT` | Jira backend | Jira project key |
| `GITLAB_TOKEN` | GitLab backend | GitLab personal access token |
| `GITLAB_PROJECT_ID` | GitLab backend | GitLab project ID |

## Advanced Usage

### Custom Test Commands

Override default test command:

```python
from strategy.ci_runner import CIRunner

class CustomRunner(CIRunner):
    def run_tests(self):
        # Custom test logic
        result = subprocess.run(["npm", "test"], ...)
        return TestResult(...)
```

### Custom Ticket Templates

Create custom bug report templates:

```python
def generate_bug_report(self, test_result, metrics):
    # Custom LLM prompt
    prompt = """
    Analyze these test failures and create a detailed bug report
    following our team's template...
    """
```

### Integration with Other Tools

#### SonarQube

```yaml
- name: Run SonarQube
  run: |
    sonar-scanner \
      -Dsonar.projectKey=$CI_PROJECT_NAME \
      -Dsonar.sources=src/
    
- name: Check Quality Gate
  run: |
    quality_gate=$(curl -s -u $SONAR_TOKEN: \
      "$SONAR_URL/api/qualitygates/project_status?analysisId=$analysisId")
    
    if [[ $(echo $quality_gate | jq -r '.projectStatus.status') != "OK" ]]; then
      strategy-pm auto loop --strategy strategy.yaml ...
    fi
```

#### Security Scans

```yaml
- name: Security Scan
  run: |
    bandit -r src/ -f json -o bandit-report.json
    safety check --json --output safety-report.json
    
    # Create tickets for security issues
    strategy-pm auto loop \
      --strategy security-strategy.yaml \
      --project .
```

## Monitoring and Alerts

### Slack Notifications

```python
import requests

def notify_slack(results):
    webhook = os.environ["SLACK_WEBHOOK_URL"]
    
    message = {
        "text": f"CI/CD Loop {'✅ Success' if results['success'] else '❌ Failed'}",
        "attachments": [{
            "fields": [
                {"title": "Iterations", "value": results['total_iterations']},
                {"title": "Tickets Created", "value": len(results['tickets_created'])}
            ]
        }]
    }
    
    requests.post(webhook, json=message)
```

### Email Notifications

```python
import smtplib
from email.mime.text import MIMEText

def notify_email(results):
    msg = MIMEText(f"""
    CI/CD Loop Results:
    
    Status: {'Success' if results['success'] else 'Failed'}
    Iterations: {results['total_iterations']}
    Tickets: {len(results['tickets_created'])}
    
    View details: {os.environ['CI_PIPELINE_URL']}
    """)
    
    server = smtplib.SMTP(os.environ['SMTP_HOST'])
    server.send_message(msg)
```

## Best Practices

1. **Start with dry-run**: Always test with `--dry-run` first
2. **Limit iterations**: Set reasonable `--max-iterations` (3-5)
3. **Monitor tickets**: Review auto-generated tickets regularly
4. **Customize prompts**: Tailor LLM prompts to your project
5. **Use separate strategies**: Different strategies for different types of failures
6. **Rate limiting**: Be mindful of API rate limits
7. **Security**: Never commit tokens to repository

## Troubleshooting

### Common Issues

1. **Backend authentication errors**
   - Check tokens are valid and have required permissions
   - Ensure environment variables are set correctly

2. **LLM not responding**
   - Check LLX installation and configuration
   - Verify model availability
   - Check network connectivity

3. **Tests not found**
   - Ensure test command matches your project
   - Check working directory is correct

4. **Tickets not created**
   - Run with `--dry-run` to check configuration
   - Check backend permissions
   - Verify project/issue tracker settings

### Debug Mode

Enable debug logging:

```bash
export STRATEGY_DEBUG=1
strategy-pm auto loop --strategy strategy.yaml .
```

### Logs

Check detailed logs:

```bash
# Docker
docker-compose logs sprintstrat-runner

# Local
tail -f ~/.local/share/strategy/logs/ci-runner.log
```

## Examples

See the `examples/` directory for complete working examples:
- `examples/github-actions/` - GitHub Actions workflow
- `examples/gitlab-ci/` - GitLab CI configuration
- `examples/jenkins/` - Jenkinsfile
- `examples/docker/` - Docker setup

## Support

- Documentation: https://strategy-pm.readthedocs.io
- Issues: https://github.com/semcod/strategy/issues
- Discussions: https://github.com/semcod/strategy/discussions
