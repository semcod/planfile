# Planfile API Reference

Complete API documentation for the Planfile SDLC automation platform.

## Table of Contents

1. [Python Library API](#python-library-api) - Use planfile as a Python package
2. [REST API](#rest-api) - Run planfile as a FastAPI server
3. [Core Components](#core-components)
4. [Backend Integration](#backend-integration)
5. [CI/CD Runner](#cicd-runner)
6. [Configuration](#configuration)
7. [Error Handling](#error-handling)
8. [Testing](#testing)

---

## Python Library API

Use planfile programmatically in your Python applications.

### Main Entry Point - `Planfile` Class

```python
from planfile import Planfile, Ticket, TicketSource

# Auto-discover .planfile/ in current or parent directories
pf = Planfile.auto_discover(".")

# Or initialize in specific directory
pf = Planfile("/path/to/project")

# Check if planfile is initialized
if pf.store.is_initialized():
    print("Planfile ready")
```

### Ticket Management

```python
from planfile import Planfile, TicketStatus

pf = Planfile.auto_discover(".")

# Create a ticket
ticket = pf.create_ticket(
    title="Fix authentication bug",
    description="Users cannot login with OAuth provider",
    priority="high",
    status="open",
    labels=["bug", "backend", "security"],
    sprint="current"
)
print(f"Created ticket: {ticket.id}")

# List tickets with filters
tickets = pf.list_tickets(
    sprint="current",           # Filter by sprint
    status="open",              # Filter by status
    priority="high"             # Filter by priority
)
for t in tickets:
    print(f"{t.id}: {t.title} [{t.status}]")

# Get single ticket
ticket = pf.get_ticket("TICKET-123")
if ticket:
    print(f"Found: {ticket.title}")

# Update ticket
updated = pf.update_ticket(
    "TICKET-123",
    status="in_progress",
    priority="critical",
    assignee="john.doe"
)

# Bulk create from external data
tickets_data = [
    {"title": "API timeout issue", "priority": "high", "labels": ["bug"]},
    {"title": "Add dark mode", "priority": "medium", "labels": ["feature"]},
    {"title": "Update docs", "priority": "low", "labels": ["docs"]},
]
created = pf.create_tickets_bulk(
    tickets_data,
    source="jira-importer",      # Source tool identifier
    sprint="sprint-42"           # Target sprint
)
print(f"Created {len(created)} tickets")
```

### Quick Ticket Helper

```python
from planfile import quick_ticket

# One-liner for tools and scripts
ticket = quick_ticket(
    title="Production alert: High memory usage",
    tool="monitoring-system",
    priority="critical",
    context={"server": "prod-01", "metric": "memory"}
)
```

### Low-Level Store Access

```python
from planfile import PlanfileStore

# Direct store access for advanced operations
store = PlanfileStore("/path/to/project")

# Initialize new planfile directory
store.init()

# CRUD operations
ticket = store.create_ticket(ticket_data)
store.update_ticket("TICKET-123", status="done")
store.delete_ticket("TICKET-123")
store.move_ticket("TICKET-123", to_sprint="sprint-5")

# ID generation
next_id = store.next_id()  # TICKET-NNN
```

---

## REST API

Run planfile as a FastAPI server for HTTP access.

### Running the Server

```bash
# Install with FastAPI support
pip install planfile
pip install fastapi uvicorn

# Start the server
uvicorn planfile.api.server:app --reload --host 0.0.0.0 --port 8000

# Or use planfile CLI
planfile server --port 8000
```

### Available Endpoints

#### Tickets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tickets` | List tickets with optional filters |
| `POST` | `/tickets` | Create new ticket |
| `GET` | `/tickets/{id}` | Get single ticket |
| `PATCH` | `/tickets/{id}` | Update ticket |
| `DELETE` | `/tickets/{id}` | Delete ticket |
| `POST` | `/tickets/{id}/move` | Move ticket to different sprint |

#### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health check |

### Example Usage

```bash
# List all tickets
curl "http://localhost:8000/tickets?sprint=current"

# Create ticket
curl -X POST "http://localhost:8000/tickets" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "API timeout fix",
    "description": "Increase timeout for external calls",
    "priority": "high",
    "sprint": "current"
  }'

# Get ticket
curl "http://localhost:8000/tickets/TICKET-123"

# Update ticket
curl -X PATCH "http://localhost:8000/tickets/TICKET-123" \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress", "priority": "critical"}'

# Move ticket to different sprint
curl -X POST "http://localhost:8000/tickets/TICKET-123/move?to_sprint=sprint-5"

# Delete ticket
curl -X DELETE "http://localhost:8000/tickets/TICKET-123"

# Health check
curl "http://localhost:8000/health"
```

### Python Client Example

```python
import httpx

# Client for planfile API
client = httpx.Client(base_url="http://localhost:8000")

# List tickets
response = client.get("/tickets", params={"sprint": "current", "status": "open"})
tickets = response.json()

# Create ticket
ticket_data = {
    "title": "Fix memory leak",
    "description": "Detected in production",
    "priority": "critical"
}
response = client.post("/tickets", json=ticket_data)
new_ticket = response.json()

# Update ticket
client.patch(f"/tickets/{new_ticket['id']}", json={"status": "in_progress"})

# Move to sprint
client.post(f"/tickets/{new_ticket['id']}/move", params={"to_sprint": "next"})
```

---

## Core Components

### Strategy Models

#### Strategy
```python
from planfile.models import Strategy

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
from planfile.models import Sprint

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
from planfile.models import TaskPattern, TaskType

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
from planfile.cli.commands import auto_loop_cli, auto_ci_status_cli

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
from planfile.cli.commands import (
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
from planfile.integrations.github import GitHubBackend

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
from planfile.integrations.jira import JiraBackend

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
from planfile.integrations.gitlab import GitLabBackend

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
from planfile.ci_runner import CIRunner

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
from planfile.ci_runner import BugAnalyzer

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
from planfile.loaders.yaml_loader import (
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
from planfile.loaders.cli_loader import (
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
from planfile.utils.metrics import (
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
from planfile.utils.priorities import (
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
from planfile.exceptions import (
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
from planfile.utils import setup_logging

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
from planfile.models import Strategy, Sprint
from planfile.loaders.yaml_loader import load_strategy

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
from planfile.integrations.github import GitHubBackend

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
from planfile.ci_runner import CIRunner

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
from planfile.integrations.github import GitHubBackend

class GitHubBackend:
    @lru_cache(maxsize=128)
    def get_issue(self, issue_id):
        # Cached issue retrieval
        pass
```

### Async Operations
```python
import asyncio
from planfile.integrations import AsyncBackend

async def create_multiple_issues(backend, issues):
    tasks = [backend.create_issue(**issue) for issue in issues]
    return await asyncio.gather(*tasks)
```

## Security

### Token Management
```python
from planfile.utils.secure import get_token, mask_token

# Secure token retrieval
token = get_token("github_token")

# Mask for logging
masked_token = mask_token(token)
logger.info(f"Using token: {masked_token}")
```

### Input Validation
```python
from pydantic import validator
from planfile.models import TaskPattern

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
from planfile.integrations.base import BaseBackend

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
from planfile.cli.commands import app

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
