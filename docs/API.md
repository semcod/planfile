# Planfile API Reference

Complete API documentation for the Planfile SDLC automation platform.

## Core Components

### Strategy Models

#### Strategy
```python
from strategy.models import Strategy

strategy = Strategy(
    name="My Project Strategy",
    project_type="web",
    domain="fintech",
    goal="Launch secure payment platform",
    sprints=[
        Sprint(
            id=1,
            name="Core Infrastructure",
            length_days=14,
            objectives=["Setup project", "Add auth"],
            tasks=[
                TaskPattern(
                    type="feature",
                    title="Setup project structure",
                    description="Create basic layout",
                    estimate=2,
                    priority="high"
                )
            ]
        )
    ]
)
```

#### Sprint
```python
from strategy.models import Sprint

sprint = Sprint(
    id=1,
    name="Foundation Sprint",
    length_days=10,
    objectives=[
        "Set up development environment",
        "Implement core features"
    ],
    tasks=[
        TaskPattern(type="feature", title="Setup CI/CD"),
        TaskPattern(type="bug", title="Fix build issues")
    ],
    quality_gates=[
        QualityGate(
            name="Test Coverage",
            type="coverage",
            threshold=80
        )
    ]
)
```

#### TaskPattern
```python
from strategy.models import TaskPattern, TaskType

task = TaskPattern(
    type=TaskType.FEATURE,
    title="Implement user authentication",
    description="Add login and registration",
    estimate=3,
    priority="high",
    dependencies=["database_setup"],
    quality_criteria=[
        "Unit tests written",
        "Security review passed"
    ]
)
```

### CLI Commands

#### Auto Commands
```python
from strategy.cli.commands import auto_loop_cli, auto_ci_status_cli

# Run auto-loop
auto_loop_cli(
    strategy="strategy.yaml",
    project=".",
    backend=["github", "jira"],
    max_iterations=5,
    auto_fix=True,
    output="results.json"
)

# Check CI status
auto_ci_status_cli(
    project=".",
    format="table"
)
```

#### Strategy Commands
```python
from strategy.cli.commands import (
    apply_strategy_cli,
    review_strategy_cli,
    validate_strategy_cli
)

# Apply strategy
apply_strategy_cli(
    strategy="strategy.yaml",
    project=".",
    backend="github",
    dry_run=False
)

# Review strategy
review_strategy_cli(
    strategy="strategy.yaml",
    project=".",
    backend="github",
    format="markdown"
)

# Validate strategy
validate_strategy_cli(
    strategy="strategy.yaml",
    schema="strict"
)
```

### Backend Integration

#### GitHub Backend
```python
from strategy.integrations.github import GitHubBackend

github = GitHubBackend(
    token="github_token",
    repo="owner/repo"
)

# Create issue
issue = github.create_issue(
    title="Bug: Authentication failure",
    body="Detailed bug description",
    labels=["bug", "high-priority"]
)

# Update issue
github.update_issue(
    issue_id=123,
    state="closed",
    comment="Fixed in PR #456"
)

# Create project card
github.create_project_card(
    project_id=1,
    column_id=2,
    content_id=issue.id,
    content_type="Issue"
)
```

#### Jira Backend
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
    summary="Authentication bug fix",
    description="Bug report details",
    issue_type="Bug",
    priority="High"
)

# Update ticket
jira.update_ticket(
    ticket_id="PROJ-123",
    status="In Progress",
    comment="Working on fix"
)

# Add comment
jira.add_comment(
    ticket_id="PROJ-123",
    body="Fix implemented, ready for review"
)
```

#### GitLab Backend
```python
from strategy.integrations.gitlab import GitLabBackend

gitlab = GitLabBackend(
    token="gitlab_token",
    project_id=123
)

# Create issue
issue = gitlab.create_issue(
    title="Fix authentication bug",
    description="Bug details",
    labels=["bug", "backend"]
)

# Update issue
gitlab.update_issue(
    issue_id=456,
    state_event="close",
    discussion="Fixed in merge request !789"
)
```

### CI/CD Runner

#### CIRunner
```python
from strategy.ci_runner import CIRunner

runner = CIRunner(
    project_path=".",
    strategy="strategy.yaml",
    backends=["github"],
    auto_fix=True
)

# Run auto-loop
results = runner.run_auto_loop(
    max_iterations=5,
    output_file="results.json"
)

# Run single iteration
result = runner.run_iteration()
```

#### BugAnalyzer
```python
from strategy.ci_runner import BugAnalyzer

analyzer = BugAnalyzer(
    llm_provider="openai",
    api_key="openai_key"
)

# Analyze test failure
bug_report = analyzer.analyze_failure(
    test_output="test failure output",
    code_context="source code",
    error_type="AssertionError"
)

# Generate fix
fix_code = analyzer.generate_fix(
    bug_report=bug_report,
    file_path="src/auth.py",
    context="authentication"
)
```

### Loaders

#### YAML Loader
```python
from strategy.loaders.yaml_loader import (
    load_strategy,
    save_strategy,
    merge_tasks
)

# Load strategy from YAML
strategy = load_strategy("strategy.yaml")

# Save strategy to YAML
save_strategy(strategy, "strategy_updated.yaml")

# Merge tasks from another file
strategy = merge_tasks(
    strategy, 
    "common_tasks.yaml"
)
```

#### JSON Loader
```python
from strategy.loaders.cli_loader import (
    load_strategy_json,
    save_strategy_json,
    export_to_markdown
)

# Load strategy from JSON
strategy = load_strategy_json("strategy.json")

# Save strategy to JSON
save_strategy_json(strategy, "strategy_updated.json")

# Export to Markdown
markdown = export_to_markdown(strategy)
```

### Utilities

#### Metrics
```python
from strategy.utils.metrics import (
    analyze_project_metrics,
    calculate_strategy_health
)

# Analyze project metrics
metrics = analyze_project_metrics(
    project_path=".",
    include_git=True,
    include_tests=True
)

# Calculate strategy health
health = calculate_strategy_health(
    strategy=strategy,
    metrics=metrics
)
```

#### Priorities
```python
from strategy.utils.priorities import (
    calculate_task_priority,
    map_priority_to_system,
    get_priority_color
)

# Calculate task priority
priority = calculate_task_priority(
    task_type="bug",
    sprint_id=1,
    base_priority="high"
)

# Map to system-specific priority
github_priority = map_priority_to_system(
    priority, 
    system="github"
)

# Get color for UI
color = get_priority_color(priority)
```

## Configuration

### Environment Variables
```bash
# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=owner/repo

# Jira
JIRA_URL=https://company.atlassian.net
JIRA_EMAIL=user@company.com
JIRA_TOKEN=ATATT3xFfGF0_xxxxxxxxxx
JIRA_PROJECT=PROJ

# GitLab
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_PROJECT_ID=123

# AI Services
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

### Configuration Files
```yaml
# ~/.planfile/config.yaml
default_backend: github
default_strategy: strategy.yaml
auto_fix: true
max_iterations: 5

backends:
  github:
    token: ${GITHUB_TOKEN}
    repo: ${GITHUB_REPO}
  
  jira:
    url: ${JIRA_URL}
    email: ${JIRA_EMAIL}
    token: ${JIRA_TOKEN}
    project: ${JIRA_PROJECT}

ai:
  provider: openai
  model: gpt-4
  temperature: 0.1
```

## Error Handling

### Exceptions
```python
from strategy.exceptions import (
    StrategyError,
    BackendError,
    ValidationError,
    ConfigurationError
)

try:
    strategy = load_strategy("strategy.yaml")
except ValidationError as e:
    print(f"Strategy validation failed: {e}")
except BackendError as e:
    print(f"Backend connection failed: {e}")
```

### Logging
```python
import logging
from strategy.utils import setup_logging

# Setup logging
setup_logging(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    file="planfile.log"
)

# Use in modules
logger = logging.getLogger(__name__)
logger.info("Starting auto-loop")
```

## Testing

### Unit Tests
```python
import pytest
from strategy.models import Strategy, Sprint
from strategy.loaders.yaml_loader import load_strategy

def test_strategy_loading():
    strategy = load_strategy("test_strategy.yaml")
    assert isinstance(strategy, Strategy)
    assert len(strategy.sprints) > 0

def test_sprint_creation():
    sprint = Sprint(id=1, name="Test Sprint", length_days=10)
    assert sprint.id == 1
    assert sprint.length_days == 10
```

### Integration Tests
```python
import pytest
from strategy.integrations.github import GitHubBackend

@pytest.mark.integration
def test_github_backend():
    backend = GitHubBackend(
        token="test_token",
        repo="test/repo"
    )
    # Test connection
    assert backend.test_connection()
```

### Mock Testing
```python
from unittest.mock import Mock, patch
from strategy.ci_runner import CIRunner

def test_auto_loop_mock():
    with patch('strategy.ci_runner.run_tests') as mock_tests:
        mock_tests.return_value = True
        
        runner = CIRunner(project_path=".")
        result = runner.run_iteration()
        
        assert result.success
        mock_tests.assert_called_once()
```

## Performance

### Caching
```python
from functools import lru_cache
from strategy.integrations.github import GitHubBackend

class GitHubBackend:
    @lru_cache(maxsize=128)
    def get_issue(self, issue_id):
        # Cached issue retrieval
        pass
```

### Async Operations
```python
import asyncio
from strategy.integrations import AsyncBackend

async def create_multiple_issues(backend, issues):
    tasks = [backend.create_issue(**issue) for issue in issues]
    return await asyncio.gather(*tasks)
```

## Security

### Token Management
```python
from strategy.utils.secure import get_token, mask_token

# Secure token retrieval
token = get_token("github_token")

# Mask for logging
masked_token = mask_token(token)
logger.info(f"Using token: {masked_token}")
```

### Input Validation
```python
from pydantic import validator
from strategy.models import TaskPattern

class TaskPattern(BaseModel):
    title: str
    
    @validator('title')
    def validate_title(cls, v):
        if len(v) < 3:
            raise ValueError("Title must be at least 3 characters")
        return v.strip()
```

## Extensibility

### Custom Backends
```python
from strategy.integrations.base import BaseBackend

class CustomBackend(BaseBackend):
    def create_issue(self, title, body, **kwargs):
        # Custom implementation
        pass
    
    def update_issue(self, issue_id, **kwargs):
        # Custom implementation
        pass
```

### Custom Commands
```python
import typer
from strategy.cli.commands import app

@app.command()
def custom_command(
    strategy_file: str = typer.Option(..., "--strategy"),
    output: str = typer.Option("output.json", "--output")
):
    """Custom CLI command"""
    strategy = load_strategy(strategy_file)
    # Custom logic
    typer.echo(f"Results saved to {output}")
```

---

**Planfile API** - Complete control over your SDLC automation. 🚀
