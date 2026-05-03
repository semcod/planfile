# Planfile

SDLC automation platform - strategic project management with CI/CD integration and automated bug-fix loops

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [Release Management (`goal.yaml`)](#release-management-goalyaml)
- [Makefile Targets](#makefile-targets)
- [Code Analysis](#code-analysis)
- [Source Map](#source-map)
- [Call Graph](#call-graph)
- [Test Contracts](#test-contracts)
- [Intent](#intent)

## Metadata

- **name**: `planfile`
- **version**: `0.1.86`
- **python_requires**: `>=3.10`
- **license**: {'text': 'Apache-2.0'}
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, testql(2), app.doql.less, goal.yaml, Dockerfile, docker-compose.yml, src(11 mod), project/(2 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: planfile;
  version: 0.1.86;
}

dependencies {
  runtime: "typer>=0.12, rich>=13.0, pydantic>=2.0, pydantic-settings>=2.0, pyyaml>=6.0, requests>=2.31, httpx>=0.27, filelock>=3.0, python-dotenv>=1.0, PyGithub>=2.0";
  dev: "pytest>=8.0, pytest-cov>=5.0, ruff>=0.5, mypy>=1.10, black>=23.0, isort>=5.12, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60";
}

entity[name="TicketSource"] {
  tool: string!;
  version: str | None;
  timestamp: datetime!;
  context: json!;
}

entity[name="Ticket"] {
  id: string!;
  name: string!;
  status: !;
  priority: string!;
  sprint: string!;
  source: TicketSource | None;
  description: string!;
  acceptance_criteria: list[str]!;
  labels: list[str]!;
  blocked_by: list[str]!;
  blocks: list[str]!;
  file: str | None;
  files: list[str]!;
  integration: list[str] | None;
  llm_hints: ModelHints | None;
  sync: json!;
  history: list[dict]!;
  created_at: datetime!;
  updated_at: datetime!;
}

entity[name="ModelHints"] {
  design: Optional[;
  implementation: Optional[;
  review: Optional[;
  triage: Optional[;
}

entity[name="Task"] {
  name: string!;
  description: string!;
  type: TaskType!;
  priority: str | None;
  model_hints: dict[str, str] | None;
  estimate: str | None;
  tags: list[str]!;
}

entity[name="Sprint"] {
  id: int | str!;
  name: string!;
  objectives: list[str]!;
  tasks: list[Task]!;
  length_days: int | None;
  duration: str | None;
  start_date: str | None;
}

entity[name="QualityGate"] {
  name: string!;
  description: str | None;
  criteria: str | list[str]!;
  required: bool!;
}

entity[name="Goal"] {
  short: string!;
  quality: list[str]!;
  delivery: list[str]!;
  metrics: list[str]!;
}

entity[name="Strategy"] {
  name: string!;
  version: str | None;
  project_type: str | None;
  domain: str | None;
  goal: str | None;
  description: str | None;
  limits: dict[str, Any]!;
  sprints: list[Sprint]!;
  tasks: dict[str, Any]!;
  quality_gates: list[QualityGate]!;
  metadata: dict[str, Any]!;
  task_types: dict[str, int]!;
}

database[name="postgres"] {
  type: postgresql;
  url: env.DATABASE_URL;
}

database[name="redis"] {
  type: redis;
  url: env.REDIS_URL;
}

interface[type="api"] {
  type: rest;
  framework: fastapi;
}

interface[type="cli"] {
  framework: argparse;
}
interface[type="cli"] page[name="planfile"] {

}

integration[name="email"] {
  type: smtp;
}

integration[name="github"] {
  type: scm;
}

workflow[name="install"] {
  trigger: manual;
  step-1: run cmd=pip install -e ".[all]";
  step-2: run cmd=pip install llx;
}

workflow[name="test"] {
  trigger: manual;
  step-1: run cmd=pytest --cov=src --cov-report=html --cov-report=term;
}

workflow[name="docker-build"] {
  trigger: manual;
  step-1: run cmd=docker build -t planfile/runner:latest .;
}

workflow[name="docker-run"] {
  trigger: manual;
  step-1: run cmd=docker-compose up -d planfile-runner;
  step-2: run cmd=docker-compose logs -f planfile-runner;
}

workflow[name="docker-stop"] {
  trigger: manual;
  step-1: run cmd=docker-compose down;
}

workflow[name="docker-clean"] {
  trigger: manual;
  step-1: run cmd=docker-compose down -v;
  step-2: run cmd=docker system prune -f;
}

workflow[name="ci-loop"] {
  trigger: manual;
  step-1: run cmd=if [ -z "$(STRATEGY)" ]; then \;
  step-2: run cmd=echo "Usage: make ci-loop STRATEGY=<strategy.yaml> [BACKENDS=github,jira] [MAX_ITERATIONS=5]"; \;
  step-3: run cmd=exit 1; \;
  step-4: run cmd=fi;
  step-5: run cmd=planfile auto loop \;
  step-6: run cmd=--strategy $(STRATEGY) \;
  step-7: run cmd=--project . \;
  step-8: run cmd=--backend $(or $(BACKENDS),github) \;
  step-9: run cmd=--max-iterations $(or $(MAX_ITERATIONS),5) \;
  step-10: run cmd=$(if $(filter true,$(AUTO_FIX)),--auto-fix) \;
  step-11: run cmd=--output ci-results.json;
}

workflow[name="dev-setup"] {
  trigger: manual;
  step-1: run cmd=python -m venv .venv;
  step-2: run cmd=source .venv/bin/activate && pip install -e ".[dev]";
  step-3: run cmd=pre-commit install;
}

workflow[name="lint"] {
  trigger: manual;
  step-1: run cmd=ruff check src/ tests/;
  step-2: run cmd=ruff format --check src/ tests/;
}

workflow[name="format"] {
  trigger: manual;
  step-1: run cmd=ruff check --fix src/ tests/;
  step-2: run cmd=ruff format src/ tests/;
}

workflow[name="example-github"] {
  trigger: manual;
  step-1: run cmd=echo "Running example with GitHub backend...";
  step-2: run cmd=echo "Make sure GITHUB_TOKEN and GITHUB_REPO are set";
  step-3: run cmd=planfile auto loop \;
  step-4: run cmd=--strategy examples/strategies/onboarding.yaml \;
  step-5: run cmd=--project . \;
  step-6: run cmd=--backend github \;
  step-7: run cmd=--max-iterations 3 \;
  step-8: run cmd=--dry-run;
}

workflow[name="example-jira"] {
  trigger: manual;
  step-1: run cmd=echo "Running example with Jira backend...";
  step-2: run cmd=echo "Make sure JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT are set";
  step-3: run cmd=planfile auto loop \;
  step-4: run cmd=--strategy examples/strategies/ecommerce-mvp.yaml \;
  step-5: run cmd=--project . \;
  step-6: run cmd=--backend jira \;
  step-7: run cmd=--max-iterations 3 \;
  step-8: run cmd=--dry-run;
}

workflow[name="status"] {
  trigger: manual;
  step-1: run cmd=planfile auto ci-status;
}

workflow[name="logs"] {
  trigger: manual;
  step-1: run cmd=docker-compose logs -f planfile-runner;
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=rm -rf .pytest_cache;
  step-2: run cmd=rm -rf htmlcov;
  step-3: run cmd=rm -rf .coverage;
  step-4: run cmd=rm -rf coverage.json;
  step-5: run cmd=rm -rf ci-results.json;
  step-6: run cmd=rm -rf test-results.xml;
  step-7: run cmd=rm -rf build;
  step-8: run cmd=rm -rf dist;
  step-9: run cmd=rm -rf *.egg-info;
}

workflow[name="version"] {
  trigger: manual;
  step-1: run cmd=python -c "import planfile; print(planfile.__version__)";
}

workflow[name="bump-patch"] {
  trigger: manual;
  step-1: run cmd=bump2version patch;
}

workflow[name="bump-minor"] {
  trigger: manual;
  step-1: run cmd=bump2version minor;
}

workflow[name="bump-major"] {
  trigger: manual;
  step-1: run cmd=bump2version major;
}

workflow[name="publish"] {
  trigger: manual;
  step-1: run cmd=python3 -m build;
  step-2: run cmd=twine upload dist/*;
}

workflow[name="pipeline-test"] {
  trigger: manual;
  step-1: run cmd=echo "Running full CI/CD pipeline locally...";
  step-2: run cmd=echo "Step 1: Install dependencies";
  step-3: run cmd=make install;
  step-4: run cmd=echo "Step 2: Run tests";
  step-5: run cmd=make test;
  step-6: run cmd=echo "Step 3: Run CI loop";
  step-7: run cmd=make ci-loop STRATEGY=examples/strategies/onboarding.yaml BACKENDS=github MAX_ITERATIONS=1;
}

workflow[name="pipeline-docker"] {
  trigger: manual;
  step-1: run cmd=echo "Running CI/CD pipeline in Docker...";
  step-2: run cmd=make docker-build;
  step-3: run cmd=docker-compose up -d;
  step-4: run cmd=sleep 10;
  step-5: run cmd=docker-compose exec planfile-runner planfile auto loop \;
  step-6: run cmd=--strategy /app/planfile.yaml \;
  step-7: run cmd=--project /workspace \;
  step-8: run cmd=--backend github \;
  step-9: run cmd=--max-iterations 1;
}

workflow[name="full-loop"] {
  trigger: manual;
  step-1: run cmd=echo "Running full bug-fix loop with auto-fix...";
  step-2: run cmd=planfile auto loop \;
  step-3: run cmd=--strategy examples/strategies/onboarding.yaml \;
  step-4: run cmd=--project . \;
  step-5: run cmd=--backend github \;
  step-6: run cmd=--max-iterations 10 \;
  step-7: run cmd=--auto-fix \;
  step-8: run cmd=--output full-loop-results.json;
}

workflow[name="strategy-review"] {
  trigger: manual;
  step-1: run cmd=planfile strategy review \;
  step-2: run cmd=--strategy examples/strategies/onboarding.yaml \;
  step-3: run cmd=--project . \;
  step-4: run cmd=--backend github;
}

workflow[name="test-github"] {
  trigger: manual;
  step-1: run cmd=echo "Testing GitHub integration...";
  step-2: run cmd=if [ -z "$(GITHUB_TOKEN)" ] || [ -z "$(GITHUB_REPO)" ]; then \;
  step-3: run cmd=echo "Set GITHUB_TOKEN and GITHUB_REPO"; \;
  step-4: run cmd=exit 1; \;
  step-5: run cmd=fi;
  step-6: run cmd=python3 -m tests.integration.test_github;
}

workflow[name="test-jira"] {
  trigger: manual;
  step-1: run cmd=echo "Testing Jira integration...";
  step-2: run cmd=if [ -z "$(JIRA_TOKEN)" ] || [ -z "$(JIRA_URL)" ]; then \;
  step-3: run cmd=echo "Set JIRA_TOKEN and JIRA_URL"; \;
  step-4: run cmd=exit 1; \;
  step-5: run cmd=fi;
  step-6: run cmd=python -m tests.integration.test_jira;
}

workflow[name="docs"] {
  trigger: manual;
  step-1: run cmd=echo "Generating documentation...";
  step-2: run cmd=cd docs && make html;
}

workflow[name="serve-docs"] {
  trigger: manual;
  step-1: run cmd=echo "Serving documentation...";
  step-2: run cmd=cd docs/_build/html && python3 -m http.server 8080;
}

workflow[name="quick-start"] {
  trigger: manual;
  step-1: run cmd=echo "Quick start with Planfile";
  step-2: run cmd=echo "==========================";
  step-3: run cmd=echo "1. Install: make install";
  step-4: run cmd=echo "2. Configure: export GITHUB_TOKEN=your_token";
  step-5: run cmd=echo "3. Run: make ci-loop STRATEGY=examples/strategies/onboarding.yaml";
  step-6: run cmd=echo "";
  step-7: run cmd=echo "For Docker: make docker-build && make docker-run";
}

workflow[name="fmt"] {
  trigger: manual;
  step-1: run cmd=ruff format .;
}

workflow[name="build"] {
  trigger: manual;
  step-1: run cmd=python -m build;
}

workflow[name="up"] {
  trigger: manual;
  step-1: run cmd=docker compose up -d;
}

workflow[name="down"] {
  trigger: manual;
  step-1: run cmd=docker compose down;
}

workflow[name="ps"] {
  trigger: manual;
  step-1: run cmd=docker compose ps;
}

workflow[name="help"] {
  trigger: manual;
  step-1: run cmd=echo "Planfile CI/CD Automation";
  step-2: run cmd=echo "============================";
  step-3: run cmd=echo "";
  step-4: run cmd=echo "Targets:";
  step-5: run cmd=echo "  install      Install Planfile with all integrations";
  step-6: run cmd=echo "  test         Run tests";
  step-7: run cmd=echo "  docker-build Build Docker image";
  step-8: run cmd=echo "  docker-run   Run Docker container";
  step-9: run cmd=echo "  ci-loop      Run CI/CD loop locally";
  step-10: run cmd=echo "  clean        Clean up artifacts";
  step-11: run cmd=echo "";
  step-12: run cmd=echo "Examples:";
  step-13: run cmd=echo "  make install                    # Install with all backends";
  step-14: run cmd=echo "  make ci-loop BACKENDS=github    # Run with GitHub only";
  step-15: run cmd=echo "  make docker-run AUTO_FIX=true   # Run with auto-fix enabled";
}

workflow[name="health"] {
  trigger: manual;
  step-1: run cmd=docker compose ps;
  step-2: run cmd=docker compose exec app echo "Health check passed";
}

workflow[name="import-makefile-hint"] {
  trigger: manual;
  step-1: run cmd=echo 'Run: taskfile import Makefile to import existing targets.';
}

workflow[name="all"] {
  trigger: manual;
  step-1: run cmd=taskfile run install;
  step-2: run cmd=taskfile run lint;
  step-3: run cmd=taskfile run test;
}

workflow[name="sumd"] {
  trigger: manual;
  step-1: run cmd=echo "# $(basename $(pwd))" > SUMD.md
echo "" >> SUMD.md
echo "$(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('description','Project description'))" 2>/dev/null || echo 'Project description')" >> SUMD.md
echo "" >> SUMD.md
echo "## Contents" >> SUMD.md
echo "" >> SUMD.md
echo "- [Metadata](#metadata)" >> SUMD.md
echo "- [Architecture](#architecture)" >> SUMD.md
echo "- [Dependencies](#dependencies)" >> SUMD.md
echo "- [Source Map](#source-map)" >> SUMD.md
echo "- [Intent](#intent)" >> SUMD.md
echo "" >> SUMD.md
echo "## Metadata" >> SUMD.md
echo "" >> SUMD.md
echo "- **name**: \`$(basename $(pwd))\`" >> SUMD.md
echo "- **version**: \`$(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('version','unknown'))" 2>/dev/null || echo 'unknown')\`" >> SUMD.md
echo "- **python_requires**: \`>=$(python3 --version 2>/dev/null | cut -d' ' -f2 | cut -d. -f1,2)\`" >> SUMD.md
echo "- **license**: $(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('license',{}).get('text','MIT'))" 2>/dev/null || echo 'MIT')" >> SUMD.md
echo "- **ecosystem**: SUMD + DOQL + testql + taskfile" >> SUMD.md
echo "- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, src/" >> SUMD.md
echo "" >> SUMD.md
echo "## Architecture" >> SUMD.md
echo "" >> SUMD.md
echo '```' >> SUMD.md
echo "SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)" >> SUMD.md
echo '```' >> SUMD.md
echo "" >> SUMD.md
echo "## Source Map" >> SUMD.md
echo "" >> SUMD.md
find . -name '*.py' -not -path './.venv/*' -not -path './venv/*' -not -path './__pycache__/*' -not -path './.git/*' | head -50 | sed 's|^./||' | sed 's|^|- |' >> SUMD.md
echo "Generated SUMD.md";
  step-2: run cmd=python3 -c "
import json, os, subprocess
from pathlib import Path
project_name = Path.cwd().name
py_files = list(Path('.').rglob('*.py'))
py_files = [f for f in py_files if not any(x in str(f) for x in ['.venv', 'venv', '__pycache__', '.git'])]
data = {
    'project_name': project_name,
    'description': 'SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization',
    'files': [{'path': str(f), 'type': 'python'} for f in py_files[:100]]
}
with open('sumd.json', 'w') as f:
    json.dump(data, f, indent=2)
print('Generated sumd.json')
" 2>/dev/null || echo 'Python generation failed, using fallback';
}

workflow[name="sumr"] {
  trigger: manual;
  step-1: run cmd=echo "# $(basename $(pwd)) - Summary Report" > SUMR.md
echo "" >> SUMR.md
echo "SUMR - Summary Report for project analysis" >> SUMR.md
echo "" >> SUMR.md
echo "## Contents" >> SUMR.md
echo "" >> SUMR.md
echo "- [Metadata](#metadata)" >> SUMR.md
echo "- [Quality Status](#quality-status)" >> SUMR.md
echo "- [Metrics](#metrics)" >> SUMR.md
echo "- [Refactoring Analysis](#refactoring-analysis)" >> SUMR.md
echo "- [Intent](#intent)" >> SUMR.md
echo "" >> SUMR.md
echo "## Metadata" >> SUMR.md
echo "" >> SUMR.md
echo "- **name**: \`$(basename $(pwd))\`" >> SUMR.md
echo "- **version**: \`$(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('version','unknown'))" 2>/dev/null || echo 'unknown')\`" >> SUMR.md
echo "- **generated_at**: \`$(date -Iseconds)\`" >> SUMR.md
echo "" >> SUMR.md
echo "## Quality Status" >> SUMR.md
echo "" >> SUMR.md
if [ -f pyqual.yaml ]; then
  echo "- **pyqual_config**: ✅ Present" >> SUMR.md
  echo "- **last_run**: $(stat -c %y .pyqual/pipeline.db 2>/dev/null | cut -d' ' -f1 || echo 'N/A')" >> SUMR.md
else
  echo "- **pyqual_config**: ❌ Missing" >> SUMR.md
fi
echo "" >> SUMR.md
echo "## Metrics" >> SUMR.md
echo "" >> SUMR.md
py_files=$(find . -name '*.py' -not -path './.venv/*' -not -path './venv/*' | wc -l)
echo "- **python_files**: $py_files" >> SUMR.md
lines=$(find . -name '*.py' -not -path './.venv/*' -not -path './venv/*' -exec cat {} \; 2>/dev/null | wc -l)
echo "- **total_lines**: $lines" >> SUMR.md
echo "" >> SUMR.md
echo "## Refactoring Analysis" >> SUMR.md
echo "" >> SUMR.md
echo "Run \`code2llm ./ -f evolution\` for detailed refactoring queue." >> SUMR.md
echo "Generated SUMR.md";
  step-2: run cmd=python3 -c "
import json, os, subprocess
from pathlib import Path
from datetime import datetime
project_name = Path.cwd().name
py_files = len([f for f in Path('.').rglob('*.py') if not any(x in str(f) for x in ['.venv', 'venv', '__pycache__', '.git'])])
data = {
    'project_name': project_name,
    'report_type': 'SUMR',
    'generated_at': datetime.now().isoformat(),
    'metrics': {
        'python_files': py_files,
        'has_pyqual_config': Path('pyqual.yaml').exists()
    }
}
with open('SUMR.json', 'w') as f:
    json.dump(data, f, indent=2)
print('Generated SUMR.json')
" 2>/dev/null || echo 'Python generation failed, using fallback';
}

deploy {
  target: docker-compose;
  compose_file: docker-compose.yml;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
  python_version: >=3.10;
}
```

### Source Modules

- `planfile.builder`
- `planfile.ci`
- `planfile.examples`
- `planfile.execution`
- `planfile.executor_standalone`
- `planfile.models`
- `planfile.runner`
- `planfile.server_common`
- `planfile.testql_integration`
- `planfile.ticket_validation`
- `planfile.todo_sync`

## Interfaces

### CLI Entry Points

- `planfile`

### testql Scenarios

#### `testql-scenarios/generated-from-pytests.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-from-pytests.testql.toon.yaml
# SCENARIO: Auto-generated from Python Tests
# TYPE: integration
# GENERATED: true

INCLUDE[2]{file}:
  "/home/tom/github/semcod/planfile/tests/test_integration.py"
  "/home/tom/github/semcod/planfile/tests/test_integration.py"
```

#### `testql-scenarios/generated-unit-tests.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-unit-tests.testql.toon.yaml
# SCENARIO: Library Unit Tests
# TYPE: unit
# GENERATED: true

LOG[2]{message}:
  "Test core functions"
  "Test public API surface"
```

## Workflows

### Taskfile Tasks (`Taskfile.yml`)

```yaml markpact:taskfile path=Taskfile.yml
version: '1'
name: planfile
description: Minimal Taskfile
variables:
  APP_NAME: planfile
environments:
  local:
    container_runtime: docker
    compose_command: docker compose
pipeline:
  python_version: "3.12"
  runner_image: ubuntu-latest
  branches: [main]
  cache: [~/.cache/pip]
  artifacts: [dist/]

  stages:
    - name: lint
      tasks: [lint]

    - name: test
      tasks: [test]

    - name: build
      tasks: [build]
      when: "branch:main"

tasks:
  install:
    desc: Install Python dependencies (editable)
    cmds:
    - pip install -e .[dev]
  test:
    desc: Run pytest suite
    cmds:
    - pytest -q
  lint:
    desc: Run ruff lint check
    cmds:
    - ruff check .
  fmt:
    desc: Auto-format with ruff
    cmds:
    - ruff format .
  build:
    desc: Build wheel + sdist
    cmds:
    - python -m build
  clean:
    desc: Remove build artefacts
    cmds:
    - rm -rf build/ dist/ *.egg-info
  up:
    desc: Start services via docker compose
    cmds:
    - docker compose up -d
  down:
    desc: Stop services
    cmds:
    - docker compose down
  logs:
    desc: Tail compose logs
    cmds:
    - docker compose logs -f
  ps:
    desc: Show running compose services
    cmds:
    - docker compose ps
  docker-build:
    desc: Build docker image
    cmds:
    - docker build -t planfile:latest .
  help:
    desc: '[imported from Makefile] help'
    cmds:
    - echo "Planfile CI/CD Automation"
    - echo "============================"
    - echo ""
    - echo "Targets:"
    - echo "  install      Install Planfile with all integrations"
    - echo "  test         Run tests"
    - echo "  docker-build Build Docker image"
    - echo "  docker-run   Run Docker container"
    - echo "  ci-loop      Run CI/CD loop locally"
    - echo "  clean        Clean up artifacts"
    - echo ""
    - echo "Examples:"
    - 'echo "  make install                    # Install with all backends"'
    - 'echo "  make ci-loop BACKENDS=github    # Run with GitHub only"'
    - 'echo "  make docker-run AUTO_FIX=true   # Run with auto-fix enabled"'
  docker-run:
    desc: '[imported from Makefile] docker-run'
    cmds:
    - docker-compose up -d planfile-runner
    - docker-compose logs -f planfile-runner
  docker-stop:
    desc: '[imported from Makefile] docker-stop'
    cmds:
    - docker-compose down
  docker-clean:
    desc: '[imported from Makefile] docker-clean'
    cmds:
    - docker-compose down -v
    - docker system prune -f
  ci-loop:
    desc: '[imported from Makefile] ci-loop'
    cmds:
    - if [ -z "$(STRATEGY)" ]; then \
    - 'echo "Usage: make ci-loop STRATEGY=<strategy.yaml> [BACKENDS=github,jira] [MAX_ITERATIONS=5]";
      \'
    - exit 1; \
    - fi
    - planfile auto loop \
    - --strategy $(STRATEGY) \
    - --project . \
    - --backend $(or $(BACKENDS),github) \
    - --max-iterations $(or $(MAX_ITERATIONS),5) \
    - $(if $(filter true,$(AUTO_FIX)),--auto-fix) \
    - --output ci-results.json
  dev-setup:
    desc: '[imported from Makefile] dev-setup'
    cmds:
    - python -m venv .venv
    - source .venv/bin/activate && pip install -e ".[dev]"
    - pre-commit install
  format:
    desc: '[imported from Makefile] format'
    cmds:
    - ruff check --fix src/ tests/
    - ruff format src/ tests/
  example-github:
    desc: '[imported from Makefile] example-github'
    cmds:
    - echo "Running example with GitHub backend..."
    - echo "Make sure GITHUB_TOKEN and GITHUB_REPO are set"
    - planfile auto loop \
    - --strategy examples/strategies/onboarding.yaml \
    - --project . \
    - --backend github \
    - --max-iterations 3 \
    - --dry-run
  example-jira:
    desc: '[imported from Makefile] example-jira'
    cmds:
    - echo "Running example with Jira backend..."
    - echo "Make sure JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT are set"
    - planfile auto loop \
    - --strategy examples/strategies/ecommerce-mvp.yaml \
    - --project . \
    - --backend jira \
    - --max-iterations 3 \
    - --dry-run
  status:
    desc: '[imported from Makefile] status'
    cmds:
    - planfile auto ci-status
  version:
    desc: '[imported from Makefile] version'
    cmds:
    - python -c "import planfile; print(planfile.__version__)"
  bump-patch:
    desc: '[imported from Makefile] bump-patch'
    cmds:
    - bump2version patch
  bump-minor:
    desc: '[imported from Makefile] bump-minor'
    cmds:
    - bump2version minor
  bump-major:
    desc: '[imported from Makefile] bump-major'
    cmds:
    - bump2version major
  publish:
    desc: '[imported from Makefile] publish'
    cmds:
    - python3 -m build
    - twine upload dist/*
  pipeline-test:
    desc: '[imported from Makefile] pipeline-test'
    cmds:
    - echo "Running full CI/CD pipeline locally..."
    - 'echo "Step 1: Install dependencies"'
    - make install
    - 'echo "Step 2: Run tests"'
    - make test
    - 'echo "Step 3: Run CI loop"'
    - make ci-loop STRATEGY=examples/strategies/onboarding.yaml BACKENDS=github MAX_ITERATIONS=1
  pipeline-docker:
    desc: '[imported from Makefile] pipeline-docker'
    cmds:
    - echo "Running CI/CD pipeline in Docker..."
    - make docker-build
    - docker-compose up -d
    - sleep 10
    - docker-compose exec planfile-runner planfile auto loop \
    - --strategy /app/planfile.yaml \
    - --project /workspace \
    - --backend github \
    - --max-iterations 1
  full-loop:
    desc: '[imported from Makefile] full-loop'
    cmds:
    - echo "Running full bug-fix loop with auto-fix..."
    - planfile auto loop \
    - --strategy examples/strategies/onboarding.yaml \
    - --project . \
    - --backend github \
    - --max-iterations 10 \
    - --auto-fix \
    - --output full-loop-results.json
  strategy-review:
    desc: '[imported from Makefile] strategy-review'
    cmds:
    - planfile strategy review \
    - --strategy examples/strategies/onboarding.yaml \
    - --project . \
    - --backend github
  test-github:
    desc: '[imported from Makefile] test-github'
    cmds:
    - echo "Testing GitHub integration..."
    - if [ -z "$(GITHUB_TOKEN)" ] || [ -z "$(GITHUB_REPO)" ]; then \
    - echo "Set GITHUB_TOKEN and GITHUB_REPO"; \
    - exit 1; \
    - fi
    - python3 -m tests.integration.test_github
  test-jira:
    desc: '[imported from Makefile] test-jira'
    cmds:
    - echo "Testing Jira integration..."
    - if [ -z "$(JIRA_TOKEN)" ] || [ -z "$(JIRA_URL)" ]; then \
    - echo "Set JIRA_TOKEN and JIRA_URL"; \
    - exit 1; \
    - fi
    - python -m tests.integration.test_jira
  docs:
    desc: '[imported from Makefile] docs'
    cmds:
    - echo "Generating documentation..."
    - cd docs && make html
  serve-docs:
    desc: '[imported from Makefile] serve-docs'
    cmds:
    - echo "Serving documentation..."
    - cd docs/_build/html && python3 -m http.server 8080
  quick-start:
    desc: '[imported from Makefile] quick-start'
    cmds:
    - echo "Quick start with Planfile"
    - echo "=========================="
    - 'echo "1. Install: make install"'
    - 'echo "2. Configure: export GITHUB_TOKEN=your_token"'
    - 'echo "3. Run: make ci-loop STRATEGY=examples/strategies/onboarding.yaml"'
    - echo ""
    - 'echo "For Docker: make docker-build && make docker-run"'
  health:
    desc: '[from doql] workflow: health'
    cmds:
    - docker compose ps
    - docker compose exec app echo "Health check passed"
  import-makefile-hint:
    desc: '[from doql] workflow: import-makefile-hint'
    cmds:
    - 'echo ''Run: taskfile import Makefile to import existing targets.'''
  all:
    desc: Run install, lint, test
    cmds:
    - taskfile run install
    - taskfile run lint
    - taskfile run test
  sumd:
    desc: Generate SUMD (Structured Unified Markdown Descriptor) for AI-aware project description
    cmds:
    - |
      echo "# $(basename $(pwd))" > SUMD.md
      echo "" >> SUMD.md
      echo "$(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('description','Project description'))" 2>/dev/null || echo 'Project description')" >> SUMD.md
      echo "" >> SUMD.md
      echo "## Contents" >> SUMD.md
      echo "" >> SUMD.md
      echo "- [Metadata](#metadata)" >> SUMD.md
      echo "- [Architecture](#architecture)" >> SUMD.md
      echo "- [Dependencies](#dependencies)" >> SUMD.md
      echo "- [Source Map](#source-map)" >> SUMD.md
      echo "- [Intent](#intent)" >> SUMD.md
      echo "" >> SUMD.md
      echo "## Metadata" >> SUMD.md
      echo "" >> SUMD.md
      echo "- **name**: \`$(basename $(pwd))\`" >> SUMD.md
      echo "- **version**: \`$(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('version','unknown'))" 2>/dev/null || echo 'unknown')\`" >> SUMD.md
      echo "- **python_requires**: \`>=$(python3 --version 2>/dev/null | cut -d' ' -f2 | cut -d. -f1,2)\`" >> SUMD.md
      echo "- **license**: $(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('license',{}).get('text','MIT'))" 2>/dev/null || echo 'MIT')" >> SUMD.md
      echo "- **ecosystem**: SUMD + DOQL + testql + taskfile" >> SUMD.md
      echo "- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, src/" >> SUMD.md
      echo "" >> SUMD.md
      echo "## Architecture" >> SUMD.md
      echo "" >> SUMD.md
      echo '```' >> SUMD.md
      echo "SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)" >> SUMD.md
      echo '```' >> SUMD.md
      echo "" >> SUMD.md
      echo "## Source Map" >> SUMD.md
      echo "" >> SUMD.md
      find . -name '*.py' -not -path './.venv/*' -not -path './venv/*' -not -path './__pycache__/*' -not -path './.git/*' | head -50 | sed 's|^./||' | sed 's|^|- |' >> SUMD.md
      echo "Generated SUMD.md"
    - |
      python3 -c "
      import json, os, subprocess
      from pathlib import Path
      project_name = Path.cwd().name
      py_files = list(Path('.').rglob('*.py'))
      py_files = [f for f in py_files if not any(x in str(f) for x in ['.venv', 'venv', '__pycache__', '.git'])]
      data = {
          'project_name': project_name,
          'description': 'SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization',
          'files': [{'path': str(f), 'type': 'python'} for f in py_files[:100]]
      }
      with open('sumd.json', 'w') as f:
          json.dump(data, f, indent=2)
      print('Generated sumd.json')
      " 2>/dev/null || echo 'Python generation failed, using fallback'
  sumr:
    desc: Generate SUMR (Summary Report) with project metrics and health status
    cmds:
    - |
      echo "# $(basename $(pwd)) - Summary Report" > SUMR.md
      echo "" >> SUMR.md
      echo "SUMR - Summary Report for project analysis" >> SUMR.md
      echo "" >> SUMR.md
      echo "## Contents" >> SUMR.md
      echo "" >> SUMR.md
      echo "- [Metadata](#metadata)" >> SUMR.md
      echo "- [Quality Status](#quality-status)" >> SUMR.md
      echo "- [Metrics](#metrics)" >> SUMR.md
      echo "- [Refactoring Analysis](#refactoring-analysis)" >> SUMR.md
      echo "- [Intent](#intent)" >> SUMR.md
      echo "" >> SUMR.md
      echo "## Metadata" >> SUMR.md
      echo "" >> SUMR.md
      echo "- **name**: \`$(basename $(pwd))\`" >> SUMR.md
      echo "- **version**: \`$(python3 -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d.get('project',{}).get('version','unknown'))" 2>/dev/null || echo 'unknown')\`" >> SUMR.md
      echo "- **generated_at**: \`$(date -Iseconds)\`" >> SUMR.md
      echo "" >> SUMR.md
      echo "## Quality Status" >> SUMR.md
      echo "" >> SUMR.md
      if [ -f pyqual.yaml ]; then
        echo "- **pyqual_config**: ✅ Present" >> SUMR.md
        echo "- **last_run**: $(stat -c %y .pyqual/pipeline.db 2>/dev/null | cut -d' ' -f1 || echo 'N/A')" >> SUMR.md
      else
        echo "- **pyqual_config**: ❌ Missing" >> SUMR.md
      fi
      echo "" >> SUMR.md
      echo "## Metrics" >> SUMR.md
      echo "" >> SUMR.md
      py_files=$(find . -name '*.py' -not -path './.venv/*' -not -path './venv/*' | wc -l)
      echo "- **python_files**: $py_files" >> SUMR.md
      lines=$(find . -name '*.py' -not -path './.venv/*' -not -path './venv/*' -exec cat {} \; 2>/dev/null | wc -l)
      echo "- **total_lines**: $lines" >> SUMR.md
      echo "" >> SUMR.md
      echo "## Refactoring Analysis" >> SUMR.md
      echo "" >> SUMR.md
      echo "Run \`code2llm ./ -f evolution\` for detailed refactoring queue." >> SUMR.md
      echo "Generated SUMR.md"
    - |
      python3 -c "
      import json, os, subprocess
      from pathlib import Path
      from datetime import datetime
      project_name = Path.cwd().name
      py_files = len([f for f in Path('.').rglob('*.py') if not any(x in str(f) for x in ['.venv', 'venv', '__pycache__', '.git'])])
      data = {
          'project_name': project_name,
          'report_type': 'SUMR',
          'generated_at': datetime.now().isoformat(),
          'metrics': {
              'python_files': py_files,
              'has_pyqual_config': Path('pyqual.yaml').exists()
          }
      }
      with open('SUMR.json', 'w') as f:
          json.dump(data, f, indent=2)
      print('Generated SUMR.json')
      " 2>/dev/null || echo 'Python generation failed, using fallback'
```

## Configuration

```yaml
project:
  name: planfile
  version: 0.1.86
  env: local
```

## Dependencies

### Runtime

```text markpact:deps python
typer>=0.12
rich>=13.0
pydantic>=2.0
pydantic-settings>=2.0
pyyaml>=6.0
requests>=2.31
httpx>=0.27
filelock>=3.0
python-dotenv>=1.0
PyGithub>=2.0
```

### Development

```text markpact:deps python scope=dev
pytest>=8.0
pytest-cov>=5.0
ruff>=0.5
mypy>=1.10
black>=23.0
isort>=5.12
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
```

## Deployment

```bash markpact:run
pip install planfile

# development install
pip install -e .[dev]
```

### Docker

- **base image**: `python:3.11-slim`
- **expose**: `11434`
- **entrypoint**: `["docker-entrypoint.sh"]`

### Docker Compose (`docker-compose.yml`)

- **planfile-runner** image=`planfile/runner:latest` ports: `11434:11434`
- **postgres** image=`postgres:15-alpine`
- **redis** image=`redis:7-alpine`
- **web-ui** image=`{'context': '.', 'dockerfile': 'Dockerfile.web'}` ports: `3000:3000`

## Release Management (`goal.yaml`)

- **versioning**: `semver`
- **commits**: `conventional` scope=`planfile`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `pyproject.toml:version`, `planfile/__init__.py:__version__`

## Makefile Targets

- `help` — Default target
- `install` — Installation
- `test` — Testing
- `docker-build` — Docker commands
- `docker-run`
- `docker-stop`
- `docker-clean`
- `ci-loop` — CI/CD commands
- `dev-setup` — Development commands
- `lint`
- `format`
- `example-github` — Examples
- `example-jira`
- `status` — Monitoring
- `logs`
- `clean` — Cleanup
- `version` — Release
- `bump-patch`
- `bump-minor`
- `bump-major`
- `publish`
- `pipeline-test` — CI/CD Pipeline helpers
- `pipeline-docker`
- `full-loop` — Advanced examples
- `strategy-review`
- `test-github` — Integration tests
- `test-jira`
- `docs` — Documentation
- `serve-docs`
- `quick-start` — Quick start

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# planfile | 239f 33390L | python:187,shell:39,javascript:6,css:6,less:1 | 2026-05-03
# stats: 545 func | 90 cls | 239 mod | CC̄=4.2 | critical:36 | cycles:0
# alerts[5]: CC handle_tool_call=27; CC ticket_bulk_update=21; CC upsert_testql_tickets=15; CC validate_strategy_yaml=14; CC main=14
# hotspots[5]: create_examples_app fan=23; sync_todo_checkboxes_from_planfile fan=22; review_strategy_cli fan=21; auto_loop_cmd fan=20; handle_tool_call fan=20
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[239]:
  app.doql.less,538
  examples/PROPOSED_API_IMPROVEMENTS.py,169
  examples/advanced-usage/ci-workflow.sh,17
  examples/advanced-usage/run.sh,30
  examples/bash-generation/test_planfile_generation.sh,278
  examples/bash-generation/verify_planfile.sh,246
  examples/checkbox-tickets/demo.py,106
  examples/checkbox-tickets/run.sh,35
  examples/cli/01_dsl_usage.py,76
  examples/cli-commands/run.sh,30
  examples/cli-commands/run_fixed.sh,36
  examples/code2llm/run.sh,110
  examples/comprehensive-example/run.sh,30
  examples/demo-without-keys/run.sh,18
  examples/ecosystem/01_full_workflow.sh,353
  examples/ecosystem/02_mcp_integration.py,382
  examples/ecosystem/03_proxy_routing.py,369
  examples/ecosystem/04_llx_integration.py,504
  examples/ecosystem/mcp-server-example.py,29
  examples/external-tools/run.sh,13
  examples/github/planfile-sync.sh,11
  examples/github/run.sh,93
  examples/gitlab/run.sh,90
  examples/htmlcov/coverage_html_cb_dd2e7eb5.js,736
  examples/htmlcov/style_cb_9ff733b0.css,390
  examples/integrated-functionality/run.sh,39
  examples/interactive-tests/htmlcov/coverage_html_cb_dd2e7eb5.js,736
  examples/interactive-tests/htmlcov/style_cb_9ff733b0.css,390
  examples/interactive-tests/test_interactive_expect.sh,279
  examples/interactive-tests/test_interactive_mode.py,151
  examples/jira/run.sh,93
  examples/llm-integration/run.sh,14
  examples/llx_validator.py,186
  examples/mcp/01_dsl_tool.py,152
  examples/multi-ticket/run.sh,167
  examples/python-api/01_basic_usage.py,113
  examples/python-api/02_ticket_management.py,173
  examples/python-api/03_integration.py,160
  examples/python-api/03_integration_simple.py,53
  examples/python-api/04_advanced_filtering.py,162
  examples/python-api/04_analytics_simple.py,60
  examples/python-api/05_dsl_usage.py,110
  examples/python-api/run_all.sh,31
  examples/quick-start/run.sh,41
  examples/quick-start/run_fixed.sh,48
  examples/readme-tests/test_readme_examples.sh,159
  examples/redup/run.sh,129
  examples/rest-api/01_start_server.sh,48
  examples/rest-api/02_curl_examples.sh,103
  examples/rest-api/03_python_client.py,251
  examples/rest-api/04_dsl_usage.py,112
  examples/rest-api/04_javascript_client.js,153
  examples/rest-api/05_integration_test.py,185
  examples/rest-api/06_websocket.py,118
  examples/rest-api/run_all.sh,50
  examples/run.sh,14
  examples/run_all_tests.sh,204
  examples/test_litellm_integration.py,367
  examples/test_llm_adapters.py,213
  examples/test_strategies.py,179
  examples/validate_with_llx.sh,66
  examples/vallm/run.sh,130
  htmlcov/coverage_html_cb_6fb7b396.js,734
  htmlcov/coverage_html_cb_dd2e7eb5.js,736
  htmlcov/style_cb_6b508a39.css,378
  htmlcov/style_cb_9ff733b0.css,390
  planfile/__init__.py,193
  planfile/analysis/__init__.py,33
  planfile/analysis/external_tools.py,269
  planfile/analysis/file_analyzer.py,128
  planfile/analysis/generator.py,348
  planfile/analysis/generators/__init__.py,24
  planfile/analysis/generators/metrics_extractor.py,45
  planfile/analysis/generators/strategy_builder.py,220
  planfile/analysis/models.py,40
  planfile/analysis/parsers/__init__.py,13
  planfile/analysis/parsers/json_parser.py,32
  planfile/analysis/parsers/text_parser.py,119
  planfile/analysis/parsers/toon_parser.py,190
  planfile/analysis/parsers/yaml_parser.py,124
  planfile/analysis/sprint_generator.py,207
  planfile/api/__init__.py,2
  planfile/api/server.py,332
  planfile/builder.py,386
  planfile/ci.py,473
  planfile/cli/__init__.py,1
  planfile/cli/__main__.py,5
  planfile/cli/auto_loop.py,27
  planfile/cli/commands.py,64
  planfile/cli/core/__init__.py,36
  planfile/cli/core/console.py,32
  planfile/cli/core/errors.py,25
  planfile/cli/core/progress.py,32
  planfile/cli/core/registry.py,68
  planfile/cli/extra_commands.py,21
  planfile/cli/groups/apply/__init__.py,12
  planfile/cli/groups/apply/commands.py,120
  planfile/cli/groups/apply/utils.py,109
  planfile/cli/groups/auto/__init__.py,19
  planfile/cli/groups/auto/commands.py,236
  planfile/cli/groups/backlog/__init__.py,19
  planfile/cli/groups/backlog/commands.py,195
  planfile/cli/groups/dsl/__init__.py,6
  planfile/cli/groups/dsl/commands.py,129
  planfile/cli/groups/examples/__init__.py,12
  planfile/cli/groups/examples/commands.py,198
  planfile/cli/groups/generate/__init__.py,19
  planfile/cli/groups/generate/commands.py,133
  planfile/cli/groups/health/__init__.py,12
  planfile/cli/groups/health/commands.py,79
  planfile/cli/groups/init/__init__.py,12
  planfile/cli/groups/init/commands.py,218
  planfile/cli/groups/query/__init__.py,23
  planfile/cli/groups/query/commands.py,245
  planfile/cli/groups/review/__init__.py,12
  planfile/cli/groups/review/commands.py,101
  planfile/cli/groups/review/utils.py,87
  planfile/cli/groups/sync/__init__.py,20
  planfile/cli/groups/sync/commands.py,175
  planfile/cli/groups/sync/core.py,257
  planfile/cli/groups/ticket/__init__.py,39
  planfile/cli/groups/ticket/commands.py,519
  planfile/cli/groups/validate/__init__.py,16
  planfile/cli/groups/validate/commands.py,161
  planfile/cli/project_detector/__init__.py,24
  planfile/cli/project_detector/base.py,35
  planfile/cli/project_detector/fallback.py,67
  planfile/cli/project_detector/gates.py,171
  planfile/cli/project_detector/git.py,37
  planfile/cli/project_detector/inference.py,81
  planfile/cli/project_detector/license.py,31
  planfile/cli/project_detector/main.py,101
  planfile/cli/project_detector/model_tier.py,61
  planfile/cli/project_detector/package.py,74
  planfile/cli/project_detector/pyproject.py,118
  planfile/cli/project_detector/readme.py,67
  planfile/cli/project_detector/structure.py,71
  planfile/cli/project_detector.py,20
  planfile/core/__init__.py,6
  planfile/core/models/__init__.py,68
  planfile/core/models/base.py,48
  planfile/core/models/strategy.py,273
  planfile/core/models/ticket.py,50
  planfile/core/models.py,8
  planfile/core/schema.py,115
  planfile/core/store.py,152
  planfile/core/store_files.py,32
  planfile/core/store_tickets.py,87
  planfile/dsl/__init__.py,22
  planfile/dsl/executor.py,337
  planfile/dsl/parser.py,206
  planfile/examples.py,140
  planfile/execution.py,6
  planfile/executor_standalone.py,339
  planfile/extensions/__init__.py,105
  planfile/importers/__init__.py,30
  planfile/importers/code2llm_importer.py,130
  planfile/importers/common.py,36
  planfile/importers/json_importer.py,15
  planfile/importers/redup_importer.py,222
  planfile/importers/vallm_importer.py,97
  planfile/importers/yaml_importer.py,15
  planfile/integrations/__init__.py,5
  planfile/integrations/base.py,2
  planfile/integrations/config.py,207
  planfile/integrations/generic.py,2
  planfile/integrations/github.py,2
  planfile/integrations/gitlab.py,2
  planfile/integrations/jira.py,2
  planfile/llm/__init__.py,2
  planfile/llm/adapters.py,76
  planfile/llm/client.py,64
  planfile/llm/generator.py,146
  planfile/llm/prompts.py,64
  planfile/loaders/__init__.py,1
  planfile/loaders/cli_loader.py,195
  planfile/loaders/yaml_loader.py,332
  planfile/mcp/__init__.py,2
  planfile/mcp/server.py,322
  planfile/models.py,22
  planfile/runner.py,419
  planfile/server_common.py,15
  planfile/sync/__init__.py,26
  planfile/sync/base.py,237
  planfile/sync/generic.py,217
  planfile/sync/github.py,239
  planfile/sync/gitlab.py,228
  planfile/sync/jira.py,285
  planfile/sync/markdown_backend/__init__.py,5
  planfile/sync/markdown_backend/backend.py,125
  planfile/sync/markdown_backend/constants.py,6
  planfile/sync/markdown_backend/files.py,25
  planfile/sync/markdown_backend/tickets.py,111
  planfile/sync/markdown_backend.py,5
  planfile/sync/mock.py,162
  planfile/sync/operations.py,261
  planfile/sync/state.py,47
  planfile/sync/utils.py,12
  planfile/testql_integration.py,712
  planfile/ticket_validation.py,363
  planfile/todo_sync.py,185
  planfile/utils/__init__.py,1
  planfile/utils/metrics.py,228
  planfile/utils/priorities.py,112
  project.sh,48
  scripts/auto_generate_planfile.sh,125
  scripts/cleanup_redundant.sh,72
  scripts/docker-entrypoint.sh,175
  scripts/project.sh,40
  scripts/run_examples.sh,287
  tests/htmlcov/coverage_html_cb_dd2e7eb5.js,736
  tests/htmlcov/style_cb_9ff733b0.css,390
  tests/llm_adapters/__init__.py,20
  tests/llm_adapters/adapters/__init__.py,10
  tests/llm_adapters/adapters/lite_llm.py,89
  tests/llm_adapters/adapters/local_llm.py,34
  tests/llm_adapters/adapters/open_router.py,99
  tests/llm_adapters/base.py,20
  tests/llm_adapters/constants.py,25
  tests/llm_adapters/models.py,14
  tests/llm_adapters.py,488
  tests/test_backlog.py,38
  tests/test_chars.py,10
  tests/test_ci_runner.py,144
  tests/test_dsl.py,372
  tests/test_e2e_backlog.py,235
  tests/test_e2e_schema.py,167
  tests/test_e2e_ticket_files.py,39
  tests/test_integration.py,8
  tests/test_regex.py,32
  tests/test_regex2.py,21
  tests/test_schema.py,163
  tests/test_strategy.py,62
  tests/test_testql_integration.py,282
  tests/test_ticket_files.py,225
  tests/test_ticket_validation.py,241
  tests/test_todo_sync.py,107
  tree.sh,2
  web/app.doql.css,361
D:
  examples/PROPOSED_API_IMPROVEMENTS.py:
    e: PlanfileStoreExtended
    PlanfileStoreExtended: stats(0),export(2),search(2)  # Extended store with analytics and export.
  examples/checkbox-tickets/demo.py:
    e: _build_summary_table,_print_sample_tickets,_print_search_results,_print_toggle_demo,demo_checkbox_tickets
    _build_summary_table(completed;pending)
    _print_sample_tickets(tickets;label;icon;style)
    _print_search_results(tickets;query)
    _print_toggle_demo(ticket)
    demo_checkbox_tickets()
  examples/cli/01_dsl_usage.py:
  examples/ecosystem/02_mcp_integration.py:
    e: run_mcp_tool,simulate_planfile_generate,simulate_planfile_apply,simulate_planfile_review,example_mcp_session,create_mcp_tool_definitions
    run_mcp_tool(tool_name;arguments)
    simulate_planfile_generate(args)
    simulate_planfile_apply(args)
    simulate_planfile_review(args)
    example_mcp_session()
    create_mcp_tool_definitions()
  examples/ecosystem/03_proxy_routing.py:
    e: example_strategy_generation_with_proxy,create_proxy_config_example,example_budget_tracking,ProxyClient
    ProxyClient: __init__(1),chat(3),get_routing_decision(2),get_usage_stats(0)  # Client for interacting with Proxym API.
    example_strategy_generation_with_proxy()
    create_proxy_config_example()
    example_budget_tracking()
  examples/ecosystem/04_llx_integration.py:
    e: example_metric_driven_planning,_calculate_complexity_score,create_llx_config_example,ProjectMetrics,LLXIntegration
    ProjectMetrics:  # Project metrics from LLX analysis.
    LLXIntegration: __init__(1),analyze_project(2),_parse_llx_output(1),_basic_analysis(1),select_model(2),get_task_scope(1)  # Integration with LLX for code analysis and model selection.
    example_metric_driven_planning()
    _calculate_complexity_score(metrics)
    create_llx_config_example()
  examples/ecosystem/mcp-server-example.py:
    e: planfile_generate,planfile_apply,planfile_review,main
    planfile_generate(arguments)
    planfile_apply(arguments)
    planfile_review(arguments)
    main()
  examples/interactive-tests/test_interactive_mode.py:
    e: run_interactive_planfile,test_interactive_mode,test_expect_script,main
    run_interactive_planfile(inputs;cwd)
    test_interactive_mode()
    test_expect_script()
    main()
  examples/llx_validator.py:
    e: create_validation_script,LLXValidator
    LLXValidator: __init__(1),validate_strategy(1),analyze_generated_code(1),_is_llx_available(0),_parse_llx_analysis(1),_basic_code_analysis(1)  # Use LLX to validate generated code and strategies.
    create_validation_script()
  examples/mcp/01_dsl_tool.py:
  examples/python-api/01_basic_usage.py:
    e: example_1_basic_initialization,example_2_create_ticket,example_3_quick_ticket,example_4_list_tickets,main
    example_1_basic_initialization()
    example_2_create_ticket()
    example_3_quick_ticket()
    example_4_list_tickets()
    main()
  examples/python-api/02_ticket_management.py:
    e: example_create_tickets,example_read_tickets,example_update_tickets,example_bulk_operations,example_delete_and_move,main
    example_create_tickets()
    example_read_tickets(ticket_ids)
    example_update_tickets(ticket_ids)
    example_bulk_operations()
    example_delete_and_move(ticket_ids)
    main()
  examples/python-api/03_integration.py:
    e: example_cli_tool_integration,example_monitoring_integration,example_ci_pipeline_integration,example_custom_decorator,main
    example_cli_tool_integration()
    example_monitoring_integration()
    example_ci_pipeline_integration()
    example_custom_decorator()
    main()
  examples/python-api/03_integration_simple.py:
    e: main
    main()
  examples/python-api/04_advanced_filtering.py:
    e: example_basic_filtering,example_combined_filters,example_search_by_labels,example_export_filtered,example_statistics,main
    example_basic_filtering()
    example_combined_filters()
    example_search_by_labels()
    example_export_filtered()
    example_statistics()
    main()
  examples/python-api/04_analytics_simple.py:
    e: main
    main()
  examples/python-api/05_dsl_usage.py:
    e: example_basic_dsl,example_parser_only,example_batch_operations,example_sprint_management,example_validation_sync,example_query_and_export
    example_basic_dsl()
    example_parser_only()
    example_batch_operations()
    example_sprint_management()
    example_validation_sync()
    example_query_and_export()
  examples/rest-api/03_python_client.py:
    e: example_basic_operations,example_bulk_operations,example_workflow,example_error_handling,main,PlanfileClient
    PlanfileClient: __init__(1),_request(2),health(0),list_tickets(3),create_ticket(5),get_ticket(1),update_ticket(1),move_ticket(2),delete_ticket(1)  # Python client for planfile REST API.
    example_basic_operations(client)
    example_bulk_operations(client)
    example_workflow(client;ticket_id)
    example_error_handling(client)
    main()
  examples/rest-api/04_dsl_usage.py:
    e: example_dsl_command,example_dsl_create_ticket,example_dsl_update_ticket,example_dsl_sprint,example_dsl_validate_sync,example_dsl_help,example_yaml_operations
    example_dsl_command()
    example_dsl_create_ticket()
    example_dsl_update_ticket()
    example_dsl_sprint()
    example_dsl_validate_sync()
    example_dsl_help()
    example_yaml_operations()
  examples/rest-api/05_integration_test.py:
    e: run_tests,TestPlanfileAPI
    TestPlanfileAPI: server(0),client(1),test_health_endpoint(1),test_create_and_get_ticket(1),test_update_ticket(1),test_list_tickets_with_filters(1),test_move_ticket(1)  # Integration tests for planfile REST API.
    run_tests()
  examples/rest-api/06_websocket.py:
    e: example_websocket_basic,example_websocket_interactive,example_websocket_error_handling,example_websocket_raw_text,example_websocket_batch,main
    example_websocket_basic()
    example_websocket_interactive()
    example_websocket_error_handling()
    example_websocket_raw_text()
    example_websocket_batch()
    main()
  examples/test_litellm_integration.py:
  examples/test_llm_adapters.py:
  examples/test_strategies.py:
    e: validate_strategy_yaml,test_strategy_generation,test_strategy_validation,main
    validate_strategy_yaml(file_path)
    test_strategy_generation(strategy_path)
    test_strategy_validation(strategy_path)
    main()
  planfile/__init__.py:
    e: quick_ticket,__getattr__,Planfile
    Planfile: __init__(1),auto_discover(2),create_ticket(1),get_ticket(1),list_tickets(0),update_ticket(1),delete_ticket(1),delete_tickets(1),create_tickets_bulk(3)  # Main entry point — convenience wrapper around PlanfileStore.
    quick_ticket(name;tool)
    __getattr__(name)
  planfile/analysis/__init__.py:
  planfile/analysis/external_tools.py:
    e: run_external_analysis,AnalysisResults,ExternalToolRunner
    AnalysisResults:  # Results from external tool analysis.
    ExternalToolRunner: __init__(1),run_all(0),run_code2llm(0),run_vallm(0),run_redup(0),parse_code2llm_output(0),parse_vallm_output(0),parse_redup_output(0),_mock_code2llm_data(0),_mock_vallm_data(0),_mock_redup_data(0)  # Runner for external code analysis tools.
    run_external_analysis(project_path)
  planfile/analysis/file_analyzer.py:
    e: FileAnalyzer
    FileAnalyzer: __init__(0),analyze_file(1),_analyze_toon(1),_analyze_yaml(1),_analyze_json(1),_analyze_text(1),_extract_from_yaml_structure(3),_extract_from_json_structure(3),analyze_directory(2),_generate_summary(3)  # Analyzes YAML/JSON files to extract issues and metrics.
  planfile/analysis/generator.py:
    e: PlanfileGenerator
    PlanfileGenerator: __init__(0),_default_limits(0),generate_with_external_tools(5),_external_to_internal_analysis(1),_extract_external_metrics(2),generate_from_analysis(6),generate_from_current_project(3),_extract_key_metrics(2),_generate_goal(3),_generate_goals(3),_generate_quality_gates(1),_generate_tasks(1),_parse_effort(1),_generate_target_metrics(1),_generate_risks(1),_generate_success_criteria(1),_create_strategy_object(1),_is_primitive(1),_serialize_primitive(1),_check_circular_ref(2),_serialize_object_attrs(2),_serialize_dict_items(2),_serialize_list_items(2),_make_serializable(2)  # Generate comprehensive planfile from file analysis.
  planfile/analysis/generators/__init__.py:
  planfile/analysis/generators/metrics_extractor.py:
    e: extract_key_metrics,_extract_cc_metrics,_extract_critical_metrics,_extract_validation_metrics,_extract_duplication_metrics,_extract_coverage_metrics
    extract_key_metrics(analysis_result;external_metrics)
    _extract_cc_metrics(analysis_result;metrics)
    _extract_critical_metrics(analysis_result;metrics)
    _extract_validation_metrics(analysis_result;metrics)
    _extract_duplication_metrics(analysis_result;metrics)
    _extract_coverage_metrics(analysis_result;metrics)
  planfile/analysis/generators/strategy_builder.py:
    e: generate_goal,generate_goals,generate_quality_gates,generate_tasks,parse_effort,generate_target_metrics,generate_risks,generate_success_criteria
    generate_goal(summary;metrics;focus_area)
    generate_goals(summary;metrics;focus_area)
    generate_quality_gates(metrics)
    generate_tasks(analysis_result)
    parse_effort(effort)
    generate_target_metrics(current)
    generate_risks(analysis_result)
    generate_success_criteria(metrics)
  planfile/analysis/models.py:
    e: ExtractedIssue,ExtractedMetric,ExtractedTask
    ExtractedIssue:  # Represents an issue extracted from a file.
    ExtractedMetric:  # Represents a metric extracted from a file.
    ExtractedTask:  # Represents a task extracted from a file.
  planfile/analysis/parsers/__init__.py:
  planfile/analysis/parsers/json_parser.py:
    e: analyze_json
    analyze_json(file_path)
  planfile/analysis/parsers/text_parser.py:
    e: analyze_text
    analyze_text(file_path)
  planfile/analysis/parsers/toon_parser.py:
    e: _parse_toon_header,_parse_toon_sections,_determine_section,_parse_health_section,_skip_section,_parse_summary_section,analyze_toon
    _parse_toon_header(line;file_path;metrics;issues)
    _parse_toon_sections(lines;file_path;metrics;issues)
    _determine_section(line;current_section)
    _parse_health_section(line;line_num;file_path;metrics;issues)
    _skip_section(line;line_num;file_path;metrics;issues)
    _parse_summary_section(line;line_num;file_path;metrics;issues)
    analyze_toon(file_path)
  planfile/analysis/parsers/yaml_parser.py:
    e: _is_issue_content,_create_issue_from_value,_process_yaml_value,_process_yaml_dict,_process_yaml_list,extract_from_yaml_structure,analyze_yaml
    _is_issue_content(value)
    _create_issue_from_value(value;full_key;path)
    _process_yaml_value(value;full_key;path;visited)
    _process_yaml_dict(data;path;parent_key;visited)
    _process_yaml_list(data;path;parent_key;visited)
    extract_from_yaml_structure(data;path;parent_key;visited)
    analyze_yaml(file_path)
  planfile/analysis/sprint_generator.py:
    e: SprintGenerator
    SprintGenerator: __init__(1),generate_sprints(2),_group_issues_by_priority(1),_get_high_and_quality_issues(1),_get_remaining_medium_issues(1),_create_sprint(5),_map_category_to_task_type(1),_get_highest_priority(1),_estimate_effort(1),generate_tickets(1)  # Generates sprints and tickets from extracted information.
  planfile/api/__init__.py:
  planfile/api/server.py:
    e: list_tickets,create_ticket,get_ticket,update_ticket,delete_ticket,move_ticket,done_ticket,start_ticket,list_sprints,create_sprint,get_yaml,patch_yaml,dsl_command,dsl_help,websocket_dsl,health,root,TicketCreate,TicketUpdate,SprintCreate,DSLRequest,DSLResponse,YAMLPatchRequest,ConnectionManager
    TicketCreate:
    TicketUpdate:
    SprintCreate:
    DSLRequest:
    DSLResponse:
    YAMLPatchRequest:
    ConnectionManager: __init__(0),connect(1),disconnect(1),broadcast(1)
    list_tickets(sprint;status;priority;source)
    create_ticket(body)
    get_ticket(ticket_id)
    update_ticket(ticket_id;body)
    delete_ticket(ticket_id)
    move_ticket(ticket_id;to_sprint)
    done_ticket(ticket_id)
    start_ticket(ticket_id)
    list_sprints()
    create_sprint(body)
    get_yaml()
    patch_yaml(body)
    dsl_command(body)
    dsl_help()
    websocket_dsl(websocket;project_path)
    health()
    root()
  planfile/builder.py:
    e: create_strategy_command,LLXStrategyBuilder
    LLXStrategyBuilder: __init__(3),_call_llx(1),ask_llm_questions(0),_parse_bullet_list(1),answers_to_strategy(1),build_strategy(1)  # Interactive strategy builder using LLX.
    create_strategy_command(output;model;local)
  planfile/ci.py:
    e: TestResult,BugReport,CIRunner
    TestResult:  # Result of running tests.
    BugReport:  # Generated bug report from test failures.
    CIRunner: __init__(7),_extract_json_object(1),run_tests(0),run_code_analysis(0),generate_bug_report(2),create_bug_tickets(1),_resolve_target_file(1),_task_patch_applied(1),_extract_yaml_object(1),auto_fix_bugs(1),check_strategy_completion(0),run_loop(0),save_results(2)  # CI/CD runner with automated bug-fix loop and ticket creation
  planfile/cli/__init__.py:
  planfile/cli/__main__.py:
  planfile/cli/auto_loop.py:
    e: create_auto_app
    create_auto_app()
  planfile/cli/commands.py:
    e: version_callback,main_callback,main
    version_callback(value)
    main_callback(version)
    main()
  planfile/cli/core/__init__.py:
  planfile/cli/core/console.py:
    e: print_success,print_error,print_warning,print_info,print_dim
    print_success(message)
    print_error(message)
    print_warning(message)
    print_info(message)
    print_dim(message)
  planfile/cli/core/errors.py:
    e: exit_with_error,exit_with_warning,handle_exception
    exit_with_error(message;code)
    exit_with_warning(message;code)
    handle_exception(e;context)
  planfile/cli/core/progress.py:
    e: with_spinner,create_progress
    with_spinner(description;fn)
    create_progress()
  planfile/cli/core/registry.py:
    e: register_simple_command,register_typer_group,CommandRegistry
    CommandRegistry: __init__(0),register(1),apply_all(1)  # Registry for CLI command groups.
    register_simple_command(app;name;command;help_text)
    register_typer_group(app;name;factory;help_text)
  planfile/cli/extra_commands.py:
    e: add_extra_commands
    add_extra_commands(app)
  planfile/cli/groups/apply/__init__.py:
    e: register_apply_commands
    register_apply_commands(app)
  planfile/cli/groups/apply/commands.py:
    e: execute_apply_strategy,display_apply_results,save_results,apply_strategy_cli
    execute_apply_strategy(strategy;project_path;backend;dry_run;sprint_ids)
    display_apply_results(results)
    save_results(results;output)
    apply_strategy_cli(strategy_path;project_path;backend;config_file;dry_run;sprint_filter;output;verbose)
  planfile/cli/groups/apply/utils.py:
    e: get_backend,load_and_validate_strategy,load_backend_config,parse_sprint_filter,select_backend
    get_backend(backend_type;config)
    load_and_validate_strategy(strategy_path)
    load_backend_config(backend;config_file)
    parse_sprint_filter(sprint_filter)
    select_backend(backend;backend_config)
  planfile/cli/groups/auto/__init__.py:
    e: register_auto_commands
    register_auto_commands(app)
  planfile/cli/groups/auto/commands.py:
    e: get_backend,_validate_strategy,_initialize_backends,_display_summary_table,_display_final_status,_display_ticket_summary,auto_loop_cmd,ci_status_cmd
    get_backend(backend_type)
    _validate_strategy(strategy)
    _initialize_backends(backend)
    _display_summary_table(results)
    _display_final_status(results;strategy)
    _display_ticket_summary(results)
    auto_loop_cmd(strategy;project_path;backend;max_iterations;auto_fix;llx_command;output;dry_run)
    ci_status_cmd(project_path)
  planfile/cli/groups/backlog/__init__.py:
    e: register_backlog_commands
    register_backlog_commands(app)
  planfile/cli/groups/backlog/commands.py:
    e: _get_planfile_yaml_path,_load_planfile_yaml,_save_planfile_yaml,_matches_files,backlog_list,create_backlog_table,_collect_backlog_to_delete,_collect_targets_to_delete,_print_deletion_preview,_execute_backlog_deletion,_execute_targets_deletion,backlog_delete
    _get_planfile_yaml_path()
    _load_planfile_yaml()
    _save_planfile_yaml(data)
    _matches_files(item;patterns)
    backlog_list(files;rule_id;fmt)
    create_backlog_table(items)
    _collect_backlog_to_delete(backlog;files;rule_id)
    _collect_targets_to_delete(data;files)
    _print_deletion_preview(to_delete;targets_to_delete)
    _execute_backlog_deletion(data;to_delete)
    _execute_targets_deletion(data;targets_to_delete)
    backlog_delete(files;rule_id;targets;dry_run;force)
  planfile/cli/groups/dsl/__init__.py:
  planfile/cli/groups/dsl/commands.py:
    e: dsl_run,_run_single,_pretty_data,_interactive_shell,register_dsl_commands
    dsl_run(command;project;fmt;fail_on_error)
    _run_single(executor;command;fmt;fail_on_error)
    _pretty_data(data)
    _interactive_shell(executor;fmt)
    register_dsl_commands(app)
  planfile/cli/groups/examples/__init__.py:
    e: register_examples_commands
    register_examples_commands(app)
  planfile/cli/groups/examples/commands.py:
    e: create_examples_app,_discover_examples,_execute_example
    create_examples_app()
    _discover_examples(examples_dir)
    _execute_example(ex)
  planfile/cli/groups/generate/__init__.py:
    e: register_generate_commands
    register_generate_commands(app)
  planfile/cli/groups/generate/commands.py:
    e: generate_strategy_cli,generate_from_files_cmd
    generate_strategy_cli(project_path;output;model;sprints;focus;toon_dir;dry_run)
    generate_from_files_cmd(project_path;output;project_name;max_sprints;focus;patterns;external_tools;compact;verbose)
  planfile/cli/groups/health/__init__.py:
    e: register_health_commands
    register_health_commands(app)
  planfile/cli/groups/health/commands.py:
    e: create_health_app
    create_health_app()
  planfile/cli/groups/init/__init__.py:
    e: register_init_commands
    register_init_commands(app)
  planfile/cli/groups/init/commands.py:
    e: _choice,_ask,_ask_list,_collect_custom_sprints,_collect_preset_sprints,_collect_sprint_data,_build_sprints_yaml,_assemble_quality_gates,_display_summary,_save_strategy,init_strategy_cli
    _choice(prompt;options;default;detected)
    _ask(prompt;default;required;detected)
    _ask_list(prompt;example)
    _collect_custom_sprints()
    _collect_preset_sprints(project_type)
    _collect_sprint_data(project_type)
    _build_sprints_yaml(sprints_data)
    _assemble_quality_gates(focus;detected_gates;extra_gates)
    _display_summary(name;project_type;domain;goal_short;sprints_yaml;focus;model_tier;output)
    _save_strategy(strategy_dict;output;yes)
    init_strategy_cli(output;yes)
  planfile/cli/groups/query/__init__.py:
    e: register_query_commands
    register_query_commands(app)
  planfile/cli/groups/query/commands.py:
    e: calculate_strategy_stats,stats_cmd,compare_strategies,compare_cmd,export_cmd,_export_to_csv,_export_to_html,merge_cmd
    calculate_strategy_stats(strategy)
    stats_cmd(strategy_file)
    compare_strategies(s1;s2)
    compare_cmd(strategy1;strategy2;output)
    export_cmd(strategy_file;format;output)
    _export_to_csv(strategy;file_path)
    _export_to_html(strategy;file_path)
    merge_cmd(strategy_files;output;name)
  planfile/cli/groups/review/__init__.py:
    e: register_review_commands
    register_review_commands(app)
  planfile/cli/groups/review/commands.py:
    e: review_strategy_cli
    review_strategy_cli(strategy_path;project_path;backend;config_file;output;verbose)
  planfile/cli/groups/review/utils.py:
    e: get_backend,_load_backend_config,_load_and_validate_strategy
    get_backend(backend_type;config)
    _load_backend_config(backend;config_file)
    _load_and_validate_strategy(strategy_path)
  planfile/cli/groups/sync/__init__.py:
    e: register_sync_commands
    register_sync_commands(app)
  planfile/cli/groups/sync/commands.py:
    e: github_cmd,gitlab_cmd,jira_cmd,markdown_cmd,handle_no_integrations,sync_all_integrations,all_cmd,_resolve_watch_integrations,_get_planfile_dir_states,_detect_changes,_run_sync_once,watch_cmd
    github_cmd(directory;dry_run;direction)
    gitlab_cmd(directory;dry_run;direction)
    jira_cmd(directory;dry_run;direction)
    markdown_cmd(directory;dry_run;direction)
    handle_no_integrations(directory;dry_run;direction)
    sync_all_integrations(integrations;directory;dry_run;direction)
    all_cmd(directory;dry_run;direction)
    _resolve_watch_integrations(config;integrations)
    _get_planfile_dir_states(planfile_dir)
    _detect_changes(last;current)
    _run_sync_once(to_sync;directory;direction)
    watch_cmd(directory;interval;integrations;direction;once)
  planfile/cli/groups/sync/core.py:
    e: _initialize_backend,_ticket_matches_integration,_collect_tickets_from_sprint,_collect_tickets_from_backlog,_ticket_matches_integration_v1,_collect_tickets_from_section,_process_planfile_v1,_load_tickets_v1_format,_load_tickets_for_sync,_execute_sync_with_progress,sync_integration
    _initialize_backend(integration_name;config;show_header)
    _ticket_matches_integration(ticket;integration_name)
    _collect_tickets_from_sprint(sprint;integration_name)
    _collect_tickets_from_backlog(backlog;integration_name)
    _ticket_matches_integration_v1(ticket;integration_name)
    _collect_tickets_from_section(data;section;integration_name)
    _process_planfile_v1(planfile_path;integration_name;all_tickets;tickets_source;v1_source_file;v1_data)
    _load_tickets_v1_format(directory;integration_name)
    _load_tickets_for_sync(store;directory;integration_name)
    _execute_sync_with_progress(backend;all_tickets;dry_run;store;integration_name;v1_source_file;v1_data;direction)
    sync_integration(integration_name;directory;dry_run;direction;show_header)
  planfile/cli/groups/ticket/__init__.py:
    e: register_ticket_commands
    register_ticket_commands(app)
  planfile/cli/groups/ticket/commands.py:
    e: _auto_sync,_display_tickets,_load_issue_records_from_file,_print_ticket_validation_table,ticket_validate,create_ticket_table,ticket_create,ticket_list,ticket_show,ticket_update,ticket_move,ticket_import,load_import_tickets,ticket_done,ticket_start,ticket_block,_collect_delete_ids,_confirm_and_delete,ticket_delete,_print_bulk_update_preview,_apply_label_changes,_execute_bulk_updates,ticket_bulk_update
    _auto_sync(directory;integrations;dry_run)
    _display_tickets(tickets;fmt)
    _load_issue_records_from_file(issues_path)
    _print_ticket_validation_table(tickets)
    ticket_validate(ticket_ids;strategy;project;issues;fmt;stale_only;fail_on_stale)
    create_ticket_table(tickets)
    ticket_create(name;priority;sprint;source;label;description;files;integration;sync;sync_dry_run)
    ticket_list(sprint;status;source;label;files;fmt)
    ticket_show(ticket_id;fmt)
    ticket_update(ticket_id;status;priority;name;sync;sync_dry_run)
    ticket_move(ticket_id;to_sprint)
    ticket_import(source;sprint;from_file)
    load_import_tickets(from_file;source)
    ticket_done(ticket_id)
    ticket_start(ticket_id)
    ticket_block(ticket_id;reason)
    _collect_delete_ids(pf;ticket_ids;sprint;status;label;source;files)
    _confirm_and_delete(pf;to_delete;dry_run;force)
    ticket_delete(ticket_ids;sprint;status;label;source;files;dry_run;force;sync;sync_dry_run)
    _print_bulk_update_preview(tickets;new_status;new_priority;add_label;remove_label;move_to_sprint)
    _apply_label_changes(ticket;base_updates;add_label;remove_label)
    _execute_bulk_updates(pf;tickets;base_updates;add_label;remove_label;move_to_sprint)
    ticket_bulk_update(sprint;status_filter;label;source;files;new_status;new_priority;add_label;remove_label;move_to_sprint;dry_run;force;sync;sync_dry_run)
  planfile/cli/groups/validate/__init__.py:
    e: register_validate_commands
    register_validate_commands(app)
  planfile/cli/groups/validate/commands.py:
    e: validate_strategy_cli,validate_schema_cli,validate_testql_cli
    validate_strategy_cli(strategy_path;verbose)
    validate_schema_cli(file_path;file_type;verbose)
    validate_testql_cli(scenario_path;project_path;url;dry_run;strategy_path;create_tickets;sync_targets;max_tickets;testql_bin;testql_repo_path)
  planfile/cli/project_detector/__init__.py:
  planfile/cli/project_detector/base.py:
    e: DetectedQualityGate,DetectedProject
    DetectedQualityGate:  # Detected quality gate from project files.
    DetectedProject:  # Container for detected project information.
  planfile/cli/project_detector/fallback.py:
    e: _detect_from_structure
    _detect_from_structure(project_path)
  planfile/cli/project_detector/gates.py:
    e: _detect_test_gates,_has_pytest_config,_detect_docker_gates,_detect_ci_gates,_detect_quality_tool_gates,_find_quality_tools,_has_ruff_config,_has_mypy_config,_detect_security_gates,_find_security_tools,_has_bandit_config,_detect_doc_gates,_detect_quality_gates
    _detect_test_gates(project_path;pyproject_data)
    _has_pytest_config(project_path;pyproject_data)
    _detect_docker_gates(project_path)
    _detect_ci_gates(project_path)
    _detect_quality_tool_gates(project_path;pyproject_data)
    _find_quality_tools(project_path;pyproject_data)
    _has_ruff_config(project_path;pyproject_data)
    _has_mypy_config(project_path;pyproject_data)
    _detect_security_gates(project_path;pyproject_data)
    _find_security_tools(project_path;pyproject_data)
    _has_bandit_config(project_path;pyproject_data)
    _detect_doc_gates(project_path)
    _detect_quality_gates(project_path;pyproject_data)
  planfile/cli/project_detector/git.py:
    e: _detect_git_authors
    _detect_git_authors(project_path)
  planfile/cli/project_detector/inference.py:
    e: _infer_python_project_type,_infer_node_project_type,_infer_domain
    _infer_python_project_type(deps;pyproject_data;project_path)
    _infer_node_project_type(deps;package_data)
    _infer_domain(keywords;classifiers;description)
  planfile/cli/project_detector/license.py:
    e: _detect_license
    _detect_license(project_path)
  planfile/cli/project_detector/main.py:
    e: detect_project,_quality_gates_to_dict,_determine_source,_build_detected_dict,get_detected_values
    detect_project(project_path)
    _quality_gates_to_dict(gates)
    _determine_source(detected)
    _build_detected_dict(detected)
    get_detected_values()
  planfile/cli/project_detector/model_tier.py:
    e: _tier_from_env_vars,_tier_from_env_files,_tier_from_config_files,_detect_model_tier
    _tier_from_env_vars()
    _tier_from_env_files(project_path)
    _tier_from_config_files(project_path)
    _detect_model_tier(project_path)
  planfile/cli/project_detector/package.py:
    e: _detect_from_package_json
    _detect_from_package_json(project_path)
  planfile/cli/project_detector/pyproject.py:
    e: _import_toml_loader,_load_pyproject_data,_populate_project_metadata,_populate_poetry_metadata,_populate_project_from_data,_get_project_dependencies,_populate_inferred_project_details,_populate_readme_and_repository_details,_detect_from_pyproject
    _import_toml_loader()
    _load_pyproject_data(pyproject_path)
    _populate_project_metadata(project;data)
    _populate_poetry_metadata(project;data)
    _populate_project_from_data(project;data)
    _get_project_dependencies(data)
    _populate_inferred_project_details(project;data;project_path)
    _populate_readme_and_repository_details(project;project_path)
    _detect_from_pyproject(project_path)
  planfile/cli/project_detector/readme.py:
    e: _extract_description,_extract_goal,_find_readme_content,_find_readme_description,_find_readme_goal
    _extract_description(lines)
    _extract_goal(content)
    _find_readme_content(project_path)
    _find_readme_description(project_path)
    _find_readme_goal(project_path)
  planfile/cli/project_detector/structure.py:
    e: _has_tests,_find_src_dirs,_suggest_sprints,_analyze_directory_structure
    _has_tests(project_path)
    _find_src_dirs(project_path)
    _suggest_sprints(project_path;src_dirs;has_tests)
    _analyze_directory_structure(project_path)
  planfile/cli/project_detector.py:
  planfile/core/__init__.py:
  planfile/core/models/__init__.py:
  planfile/core/models/base.py:
    e: TaskType,ModelTier,TicketStatus
    TaskType:  # Type of task in the planfile.
    ModelTier:  # Model tier for different phases of work.
    TicketStatus:  # Status of a ticket.
  planfile/core/models/strategy.py:
    e: ModelHints,Task,Sprint,QualityGate,Goal,Strategy
    ModelHints: convert_str_to_tier(2)  # AI model hints for different phases of task execution.
    Task: normalize_model_hints(2)  # A task in a sprint - simplified and directly embedded.
    Sprint: convert_tasks(2)  # A sprint in the planfile.
    QualityGate: normalize_criteria(2)  # Quality gate definition.
    Goal:  # Project goal definition.
    Strategy: get_task_patterns(1),get_sprint(1),validate_sprint_ids(2),compare(1),merge(2),export(1),_count_task_types(0),_collect_durations(0),get_stats(0),to_yaml(0)  # Main strategy configuration - simplified and more flexible.
  planfile/core/models/ticket.py:
    e: TicketSource,Ticket
    TicketSource:  # Who/what created the ticket.
    Ticket:  # Atomic unit of work in planfile.
  planfile/core/models.py:
  planfile/core/schema.py:
    e: validate_yaml_file,SchemaValidator
    SchemaValidator: validate_planfile(2),validate_sprint(2),get_current_schema_version(1)  # Validate planfile YAML files against schema definitions.
    validate_yaml_file(file_path;file_type)
  planfile/core/store.py:
    e: Store
    Store: __init__(1),is_initialized(0),init(0),_read_config(0),_write_config(1),next_id(0),_sprint_file(1),_all_sprint_files(0),create_ticket(1),get_ticket(1),update_ticket(1),delete_ticket(1),delete_tickets_bulk(1)  # File-based ticket store using .planfile/ directory.
  planfile/core/store_files.py:
    e: StoreFileMixin
    StoreFileMixin: _sprint_file(1),_all_sprint_files(0),_read_yaml_cached(1)
  planfile/core/store_tickets.py:
    e: TicketStoreMixin
    TicketStoreMixin: _ticket_from_data(1),_tickets_from_sprint_data(1),_filter_by_files(2),_filter_by_labels(2),_filter_by_attribute(3),_apply_filters(1),_matches_files(2),list_tickets(1)
  planfile/dsl/__init__.py:
  planfile/dsl/executor.py:
    e: DSLResult,DSLExecutor
    DSLResult: to_dict(0)
    DSLExecutor: __init__(1),pf(0),run(1),execute(1),_exec_help(1),_exec_unknown(1),_exec_create(1),_exec_create_sprint(1),_exec_list(1),_exec_list_sprints(1),_exec_show(1),_exec_update(1),_exec_move(1),_exec_done(1),_exec_start(1),_exec_block(1),_exec_delete(1),_exec_validate(1),_exec_sync(1),_exec_query(1),_exec_export(1)  # Execute DSL commands against a Planfile instance.
  planfile/dsl/parser.py:
    e: DSLCommand,DSLParser
    DSLCommand: is_valid(0),to_dict(0)
    DSLParser: parse(1),_extract_object(2),_extract_target(2),_extract_modifiers(2),_coerce(1)  # Parse natural language / DSL commands into DSLCommand object
  planfile/examples.py:
    e: example_create_strategy,example_validate_strategy,example_run_strategy,example_verify_strategy,example_programmatic_strategy
    example_create_strategy()
    example_validate_strategy()
    example_run_strategy()
    example_verify_strategy()
    example_programmatic_strategy()
  planfile/execution.py:
  planfile/executor_standalone.py:
    e: create_openai_client,create_litellm_client,execute_strategy,TaskResult,LLMClient,StrategyExecutor
    TaskResult:  # Result of executing a task.
    LLMClient: __init__(2),chat(2)  # Simple LLM client interface.
    StrategyExecutor: __init__(2),_default_config(0),execute_strategy(2),_execute_task(4),_select_model(1),_build_prompt(2),_get_project_metrics(1)  # Standalone strategy executor.
    create_openai_client(api_key;model)
    create_litellm_client(api_key;model)
    execute_strategy(strategy_path;project_path)
  planfile/extensions/__init__.py:
    e: TicketLogger
    TicketLogger: __init__(2),error(4),warning(2),metric_alert(4),catch_errors(1)  # Logger that creates tickets for errors, warnings, and alerts
  planfile/importers/__init__.py:
    e: register_importer,import_from_source
    register_importer(name;importer_cls)
    import_from_source(path;source)
  planfile/importers/code2llm_importer.py:
    e: import_code2llm,_parse_evolution,_evolution_item_to_ticket,_parse_health,EvolutionParser
    EvolutionParser: __init__(1),parse(1),_process_line(1),_handle_outside(1),_handle_in_next(1)  # State machine parser for evolution.toon NEXT[] sections.
    import_code2llm(toon_path;auto_priority;sprint)
    _parse_evolution(content;auto_priority)
    _evolution_item_to_ticket(item;auto_priority)
    _parse_health(content;auto_priority)
  planfile/importers/common.py:
    e: normalize_ticket_dict,load_structured_tickets
    normalize_ticket_dict(item)
    load_structured_tickets(path;loader)
  planfile/importers/json_importer.py:
    e: import_json
    import_json(path)
  planfile/importers/redup_importer.py:
    e: import_redup,_parse_toon_format,_parse_duplicates,_parse_refactor,_create_refactor_ticket
    import_redup(file_path)
    _parse_toon_format(content)
    _parse_duplicates(text)
    _parse_refactor(text)
    _create_refactor_ticket(item;index)
  planfile/importers/vallm_importer.py:
    e: import_vallm,_auto_labels,VallmParser
    VallmParser: __init__(1),parse(1),_process_line(1),_is_file_entry(1),_is_issue_entry(1),_parse_file_entry(1),_parse_issue_entry(1),_determine_priority(1)  # Parser for vallm validation.toon files.
    import_vallm(toon_path;auto_priority)
    _auto_labels(rule)
  planfile/importers/yaml_importer.py:
    e: import_yaml
    import_yaml(path)
  planfile/integrations/__init__.py:
  planfile/integrations/base.py:
  planfile/integrations/config.py:
    e: IntegrationConfig
    IntegrationConfig: __init__(1),load_dotenv(0),_expand_env_vars(1),discover_configs(0),load_configs(0),get_integration_config(1),get_project_config(0),get_sprint_config(0),get_backlog_config(0),_deep_merge(2),validate_integration(1),has_configured_integrations(0),get_default_backend(0),get_integration_backend(1)  # Manages integration configuration with support for multiple 
  planfile/integrations/generic.py:
  planfile/integrations/github.py:
  planfile/integrations/gitlab.py:
  planfile/integrations/jira.py:
  planfile/llm/__init__.py:
  planfile/llm/adapters.py:
    e: LLMTestResult,BaseLLMAdapter,LiteLLMAdapter,OpenRouterAdapter,LocalLLMAdapter,LLMTestRunner
    LLMTestResult:
    BaseLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)
    LiteLLMAdapter:
    OpenRouterAdapter:
    LocalLLMAdapter:
    LLMTestRunner: __init__(0),register_adapter(2)
  planfile/llm/client.py:
    e: call_llm
    call_llm(prompt;model;temperature)
  planfile/llm/generator.py:
    e: generate_strategy,_collect_metrics,_auto_select_model,_parse_strategy_response,_fix_yaml_formatting,_basic_metrics
    generate_strategy(project_path)
    _collect_metrics(project_path;toon_dir)
    _auto_select_model(metrics)
    _parse_strategy_response(response)
    _fix_yaml_formatting(yaml_text)
    _basic_metrics(project_path)
  planfile/llm/prompts.py:
    e: build_strategy_prompt
    build_strategy_prompt(metrics;sprints;focus)
  planfile/loaders/__init__.py:
  planfile/loaders/cli_loader.py:
    e: load_from_json,save_to_json,load_strategy_from_json,save_strategy_to_json,_md_header,_md_summary,_md_tasks,_md_sprints,_md_metrics,export_results_to_markdown
    load_from_json(file_path)
    save_to_json(data;file_path)
    load_strategy_from_json(file_path)
    save_strategy_to_json(strategy;file_path)
    _md_header(results)
    _md_summary(results)
    _md_tasks(results)
    _md_sprints(results)
    _md_metrics(results)
    export_results_to_markdown(results;file_path)
  planfile/loaders/yaml_loader.py:
    e: load_yaml,save_yaml,load_strategy_yaml,_transform_task_patterns,_transform_sprints,_transform_goal,_format_validation_error,save_strategy_yaml,load_tasks_yaml,merge_strategy_with_tasks,_check_required_keys,_validate_sprints,_validate_gates,_validate_task_patterns,validate_strategy_schema
    load_yaml(file_path)
    save_yaml(data;file_path)
    load_strategy_yaml(file_path)
    _transform_task_patterns(data)
    _transform_sprints(data)
    _transform_goal(data)
    _format_validation_error(e;file_path)
    save_strategy_yaml(strategy;file_path)
    load_tasks_yaml(file_path)
    merge_strategy_with_tasks(strategy;tasks_file)
    _check_required_keys(data;issues)
    _validate_sprints(data;issues)
    _validate_gates(data;issues)
    _validate_task_patterns(data;issues)
    validate_strategy_schema(file_path)
  planfile/mcp/__init__.py:
  planfile/mcp/server.py:
    e: handle_tool_call,_read_jsonrpc,_write_jsonrpc,main
    handle_tool_call(name;arguments)
    _read_jsonrpc()
    _write_jsonrpc(obj)
    main()
  planfile/models.py:
  planfile/runner.py:
    e: load_valid_strategy,verify_strategy_post_execution,_get_project_hash,analyze_project_metrics,apply_strategy_to_tickets,review_strategy,run_strategy
    load_valid_strategy(path)
    verify_strategy_post_execution(strategy;project_path;backend)
    _get_project_hash(project_path)
    analyze_project_metrics(project_path)
    apply_strategy_to_tickets(strategy;project_path;backend;dry_run)
    review_strategy(strategy;project_path;backends;backend_name)
    run_strategy(strategy_path;project_path;backend;dry_run)
  planfile/server_common.py:
    e: get_planfile
    get_planfile(start_path)
  planfile/sync/__init__.py:
  planfile/sync/base.py:
    e: TicketRef,TicketState,PMBackend,BasePMBackend
    TicketRef:  # Reference to a created/updated ticket.
    TicketState:  # State snapshot of a ticket.
    PMBackend: create_ticket(1),update_ticket(0),get_ticket(1),list_tickets(0),search_tickets(1)  # Protocol for PM system backends.
    BasePMBackend: __init__(1),_validate_config(0),map_priority(1),prepare_metadata(1),create_ticket(1),_create_ticket(6),update_ticket(7),_update_ticket(7),get_ticket(1),_get_ticket(1),list_tickets(4),_list_tickets(4),search_tickets(1),_search_tickets(1),build_ticket_ref(0),build_ticket_state(0)  # Base class for PM backends with common functionality.
  planfile/sync/generic.py:
    e: GenericBackend
    GenericBackend: __init__(3),_validate_config(0),_make_request(4),_create_ticket(6),_update_ticket(7),_build_update_data(6),_get_ticket(1),_list_tickets(4),_search_tickets(1),_ticket_data_to_status(1)  # Generic HTTP API backend for PM systems.
  planfile/sync/github.py:
    e: GitHubBackend
    GitHubBackend: __init__(2),_validate_config(0),_ensure_labels_exist(1),_prepare_labels(2),_build_metadata_body(2),_create_ticket(7),_update_labels(3),_update_issue_state(2),_update_ticket(8),_get_ticket(1),_issue_to_ticket_status(1),_list_tickets(5),_search_tickets(1)  # GitHub Issues integration backend.
  planfile/sync/gitlab.py:
    e: GitLabBackend
    GitLabBackend: __init__(3),_validate_config(0),_prepare_labels(2),_build_metadata_body(2),_create_ticket(7),_update_labels(3),_update_state(2),_update_ticket(8),_get_ticket(1),_issue_to_ticket_status(1),_list_tickets(5),_search_tickets(1)  # GitLab Issues integration backend.
  planfile/sync/jira.py:
    e: JiraBackend
    JiraBackend: __init__(4),_validate_config(0),map_priority(1),_map_task_type_to_jira(1),_build_metadata_section(1),_create_ticket(6),_build_update_fields(4),_transition_issue(2),_update_ticket(7),_get_ticket(1),_issue_to_ticket_status(1),_list_tickets(4),_search_tickets(1)  # Jira integration backend.
  planfile/sync/markdown_backend/__init__.py:
  planfile/sync/markdown_backend/backend.py:
    e: MarkdownFileBackend
    MarkdownFileBackend: __init__(2),_create_ticket(6),_update_ticket(7),_get_ticket(1),_list_tickets(4),_search_tickets(1),_find_ticket_file(1),_scan_ticket_ids(0)  # Backend for managing tickets in CHANGELOG.md and TODO.md fil
  planfile/sync/markdown_backend/constants.py:
  planfile/sync/markdown_backend/files.py:
    e: MarkdownFileManager
    MarkdownFileManager: _ensure_files_exist(0)  # File existence and bootstrap helpers for markdown ticket fil
  planfile/sync/markdown_backend/tickets.py:
    e: MarkdownTicketHelpers
    MarkdownTicketHelpers: _determine_target_file(3),_generate_ticket_id(2),_ticket_exists(2),_ticket_exists_by_title(2),_format_ticket_entry(7),_write_ticket_to_file(2)  # Ticket routing, lookup, formatting, and persistence helpers.
  planfile/sync/markdown_backend.py:
  planfile/sync/mock.py:
    e: MockBackend
    MockBackend: __init__(0),_create_ticket(6),_update_ticket(7),_get_ticket(1),_list_tickets(4),_search_tickets(1)  # Mock backend for examples and testing that doesn't require a
  planfile/sync/operations.py:
    e: sync_to_external,_update_existing_ticket,_create_new_ticket,_is_permission_error,_print_permission_error,_save_sync_results,_load_sprint_and_backlog,_fetch_external_tickets,_process_external_ticket,sync_from_external,_extract_ticket_data,_print_dry_run_action,_update_local_ticket,_import_new_ticket,_save_import_results
    sync_to_external(backend;tickets;dry_run;store;integration_name;v1_source_file;v1_data)
    _update_existing_ticket(backend;ticket;ticket_id;external_id;integration_name;sync_state)
    _create_new_ticket(backend;ticket;ticket_id;integration_name;sync_state;ticket_map)
    _is_permission_error(e)
    _print_permission_error(ticket_id)
    _save_sync_results(store;v1_source_file;v1_data)
    _load_sprint_and_backlog(store;v1_source_file;v1_data)
    _fetch_external_tickets(backend;integration_name)
    _process_external_ticket(ext_ticket;sprint;backlog;sync_state;integration_name;dry_run;imported_count;updated_count)
    sync_from_external(backend;store;dry_run;integration_name;v1_source_file;v1_data)
    _extract_ticket_data(ext_ticket)
    _print_dry_run_action(planfile_id;ext_data)
    _update_local_ticket(sprint;backlog;planfile_id;ext_data;updated_count)
    _import_new_ticket(backlog;ext_data;integration_name;sync_state;imported_count)
    _save_import_results(store;v1_source_file;v1_data;sprint;backlog;imported_count;updated_count)
  planfile/sync/state.py:
    e: SyncState
    SyncState: __init__(2),get_last_sync(0),save_sync(1),get_remote_id(1),get_local_id(1)  # Persist mapping between local ticket IDs and remote IDs.
  planfile/sync/utils.py:
    e: save_v1_format
    save_v1_format(file_path;data)
  planfile/testql_integration.py:
    e: _normalize_ref_text,_normalize_ref_url,_iter_external_refs,_collect_ticket_identity_keys,_collect_external_ref_candidates,_extract_result_field,_extract_created_ticket_ref,_extract_search_ticket_id,_looks_not_found_error,_looks_already_exists_error,_update_existing_ref_entry,_append_ref_entry,_update_ticket_integration_fields,_attach_external_ref,_resolve_update_reference,_extract_json_payload,_resolve_scenario_path,_resolve_testql_executable,run_testql_validation,_collect_step_messages,_collect_error_messages,_dedupe_messages,_collect_failure_messages,_extract_file_from_message,build_testql_tickets,_default_strategy_payload,_load_or_init_strategy,_ensure_strategy_lists,_build_task_pattern_entry,_upsert_single_ticket,upsert_testql_tickets,_resolve_sync_backend,_sync_ticket_to_backend,_sync_tickets_to_integration,sync_testql_tickets
    _normalize_ref_text(value)
    _normalize_ref_url(value)
    _iter_external_refs(ticket)
    _collect_ticket_identity_keys(ticket)
    _collect_external_ref_candidates(ticket;integration)
    _extract_result_field(result;field)
    _extract_created_ticket_ref(result)
    _extract_search_ticket_id(item)
    _looks_not_found_error(exc)
    _looks_already_exists_error(exc)
    _update_existing_ref_entry(refs;integration;ref_id;ref_key;ref_url)
    _append_ref_entry(refs;integration;ref_id;ref_key;ref_url)
    _update_ticket_integration_fields(ticket;integration;ref_id;ref_key;ref_url)
    _attach_external_ref(ticket;integration;ref)
    _resolve_update_reference(backend;ticket;integration)
    _extract_json_payload(text)
    _resolve_scenario_path(scenario_path;project_root)
    _resolve_testql_executable(testql_bin;testql_repo_path)
    run_testql_validation(scenario_path;project_path)
    _collect_step_messages(steps_raw)
    _collect_error_messages(errors_raw)
    _dedupe_messages(messages)
    _collect_failure_messages(report)
    _extract_file_from_message(message)
    build_testql_tickets(report;scenario_path)
    _default_strategy_payload()
    _load_or_init_strategy(strategy_file)
    _ensure_strategy_lists(strategy)
    _build_task_pattern_entry(ticket;ticket_id)
    _upsert_single_ticket(ticket;tasks;task_patterns;existing_task_ids;existing_pattern_ids;existing_identity_keys)
    upsert_testql_tickets(strategy_path;tickets)
    _resolve_sync_backend(config;integration)
    _sync_ticket_to_backend(ticket;backend;integration)
    _sync_tickets_to_integration(tickets;backend;integration)
    sync_testql_tickets(tickets)
  planfile/ticket_validation.py:
    e: _load_strategy,_normalize_rule,_normalize_rel_path,_normalize_files,_resolve_ticket_id,_iter_tasks_list,_iter_tickets_dict,_collect_ticket_entries,_parse_positive_int,_normalize_ticket_filters,_build_issue_indexes,_count_file_lines,_validate_rule_anchor,_resolve_existing_files,_validate_line_anchor,_validate_file_only,_validate_ticket,validate_planfile_tickets
    _load_strategy(path)
    _normalize_rule(value)
    _normalize_rel_path(value;project_root)
    _normalize_files(ticket;project_root)
    _resolve_ticket_id(ticket;entry_ref)
    _iter_tasks_list(items;base_ref)
    _iter_tickets_dict(items;base_ref)
    _collect_ticket_entries(strategy)
    _parse_positive_int(value)
    _normalize_ticket_filters(ticket_ids)
    _build_issue_indexes(issue_records;project_root)
    _count_file_lines(abs_path)
    _validate_rule_anchor(record;rule_id;files;rule_file_index;scan_available)
    _resolve_existing_files(files;project_root)
    _validate_line_anchor(record;files;line;project_root;file_line_index;scan_available)
    _validate_file_only(record;files;project_root)
    _validate_ticket(ticket;entry_ref;project_root;rule_file_index;file_line_index;scan_available)
    validate_planfile_tickets(strategy_path;project_path)
  planfile/todo_sync.py:
    e: _load_strategy,_status_done,_get_value,_normalize_marker,_collect_markers_from_results,_collect_markers_from_strategy,_resolve_todo_config,_line_matches_any_marker,sync_todo_checkboxes_from_planfile
    _load_strategy(path)
    _status_done(status)
    _get_value(item;key)
    _normalize_marker(value)
    _collect_markers_from_results(results)
    _collect_markers_from_strategy(strategy)
    _resolve_todo_config(strategy;strategy_path;project_path;enabled_override)
    _line_matches_any_marker(body;markers)
    sync_todo_checkboxes_from_planfile(strategy_path;project_path)
  planfile/utils/__init__.py:
  planfile/utils/metrics.py:
    e: _collect_git_metrics,_count_files_by_language,_check_project_files,analyze_project_metrics,calculate_strategy_health
    _collect_git_metrics(path)
    _count_files_by_language(path)
    _check_project_files(path)
    analyze_project_metrics(project_path)
    calculate_strategy_health(strategy_results)
  planfile/utils/priorities.py:
    e: calculate_task_priority,map_priority_to_system,get_priority_color
    calculate_task_priority(base_priority;task_type;sprint_id;weight_factors)
    map_priority_to_system(priority;system)
    get_priority_color(priority)
  tests/llm_adapters/__init__.py:
  tests/llm_adapters/adapters/__init__.py:
  tests/llm_adapters/adapters/lite_llm.py:
    e: LiteLLMAdapter
    LiteLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Adapter for LiteLLM providers.
  tests/llm_adapters/adapters/local_llm.py:
    e: LocalLLMAdapter
    LocalLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Adapter for local LLM servers (Ollama, LM Studio, etc.).
  tests/llm_adapters/adapters/open_router.py:
    e: OpenRouterAdapter
    OpenRouterAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Adapter for OpenRouter API.
  tests/llm_adapters/base.py:
    e: BaseLLMAdapter
    BaseLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Base class for LLM adapters.
  tests/llm_adapters/constants.py:
  tests/llm_adapters/models.py:
    e: LLMTestResult
    LLMTestResult:  # Result of LLM test.
  tests/llm_adapters.py:
    e: LLMTestResult,BaseLLMAdapter,LiteLLMAdapter,OpenRouterAdapter,LocalLLMAdapter,LLMTestRunner
    LLMTestResult:  # Result of LLM test.
    BaseLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Base class for LLM adapters.
    LiteLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Adapter for LiteLLM providers.
    OpenRouterAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Adapter for OpenRouter API.
    LocalLLMAdapter: __init__(1),test_strategy_generation(2),_test_ollama(2),_test_openai_compatible(2),get_available_models(0)  # Adapter for local LLM servers (Ollama, LM Studio, etc.).
    LLMTestRunner: __init__(0),register_adapter(2),test_strategy_with_all_adapters(2),generate_report(1),_generate_header(0),_generate_summary_table(1),_generate_detailed_results(1),_generate_successful_tests_section(1),_generate_failed_tests_section(1)  # Run tests across multiple LLM adapters.
  tests/test_backlog.py:
    e: test_backlog_list_no_items,test_matches_files
    test_backlog_list_no_items()
    test_matches_files()
  tests/test_chars.py:
  tests/test_ci_runner.py:
    e: _make_runner,test_generate_bug_report_accepts_title_key,test_generate_bug_report_parses_markdown_json,test_auto_fix_bugs_uses_llx_plan_run_with_edit_backend,test_auto_fix_bugs_returns_false_without_target_file
    _make_runner(auto_fix)
    test_generate_bug_report_accepts_title_key(monkeypatch)
    test_generate_bug_report_parses_markdown_json(monkeypatch)
    test_auto_fix_bugs_uses_llx_plan_run_with_edit_backend(monkeypatch;tmp_path)
    test_auto_fix_bugs_returns_false_without_target_file(monkeypatch;tmp_path)
  tests/test_dsl.py:
    e: _make_mock_ticket,TestDSLParser,TestDSLExecutor
    TestDSLParser: setup_method(0),test_parse_empty(0),test_parse_help(0),test_parse_unknown_verb(0),test_parse_list_tickets(0),test_parse_list_tickets_with_filters(0),test_parse_list_sprints(0),test_parse_create_ticket_quoted(0),test_parse_create_ticket_sprint(0),test_parse_create_aliases(0),test_parse_show_ticket(0),test_parse_ticket_id_uppercase(0),test_parse_update_ticket(0),test_parse_set_alias(0),test_parse_set_labels(0),test_parse_move_ticket(0),test_parse_move_ticket_to_value(0),test_parse_done(0),test_parse_done_aliases(0),test_parse_start(0),test_parse_block(0),test_parse_delete(0),test_parse_delete_aliases(0),test_parse_validate(0),test_parse_sync(0),test_parse_sync_all(0),test_parse_query_where(0),test_parse_export(0),test_coerce_bool_true(0),test_coerce_bool_false(0),test_coerce_int(0),test_to_dict(0),test_is_valid(0)
    TestDSLExecutor: _executor_with_mock(0),test_help(0),test_unknown_verb(0),test_list_tickets(0),test_list_tickets_empty(0),test_create_ticket(0),test_create_ticket_missing_name(0),test_show_ticket(0),test_show_ticket_not_found(0),test_show_ticket_missing_id(0),test_update_ticket(0),test_update_ticket_no_params(0),test_update_ticket_not_found(0),test_done_ticket(0),test_start_ticket(0),test_block_ticket(0),test_block_ticket_with_reason(0),test_delete_ticket(0),test_delete_ticket_not_found(0),test_move_ticket(0),test_move_ticket_missing_sprint(0),test_dsl_result_to_dict(0),test_query_delegates_to_list(0),test_executor_handles_exception(0)
    _make_mock_ticket(ticket_id;name;status;priority)
  tests/test_e2e_backlog.py:
    e: test_e2e_backlog_list_empty,test_e2e_backlog_list_with_items,test_e2e_backlog_list_with_files_filter,test_e2e_backlog_delete_dry_run,test_e2e_backlog_delete_force,test_e2e_backlog_delete_targets
    test_e2e_backlog_list_empty()
    test_e2e_backlog_list_with_items()
    test_e2e_backlog_list_with_files_filter()
    test_e2e_backlog_delete_dry_run()
    test_e2e_backlog_delete_force()
    test_e2e_backlog_delete_targets()
  tests/test_e2e_schema.py:
    e: test_e2e_validate_schema_valid_planfile,test_e2e_validate_schema_missing_required_field,test_e2e_validate_schema_version_mismatch,test_e2e_validate_schema_invalid_yaml,test_e2e_validate_schema_sprint_yaml,test_e2e_validate_schema_verbose
    test_e2e_validate_schema_valid_planfile()
    test_e2e_validate_schema_missing_required_field()
    test_e2e_validate_schema_version_mismatch()
    test_e2e_validate_schema_invalid_yaml()
    test_e2e_validate_schema_sprint_yaml()
    test_e2e_validate_schema_verbose()
  tests/test_e2e_ticket_files.py:
    e: test_e2e_ticket_create_with_files,test_e2e_ticket_list_with_files_filter,test_e2e_ticket_delete_with_files_filter,test_e2e_ticket_bulk_update_with_files_filter,test_e2e_ticket_with_single_file_field
    test_e2e_ticket_create_with_files()
    test_e2e_ticket_list_with_files_filter()
    test_e2e_ticket_delete_with_files_filter()
    test_e2e_ticket_bulk_update_with_files_filter()
    test_e2e_ticket_with_single_file_field()
  tests/test_integration.py:
    e: test_integration
    test_integration()
  tests/test_regex.py:
  tests/test_regex2.py:
  tests/test_schema.py:
    e: test_validate_planfile_valid,test_validate_planfile_missing_required_field,test_validate_planfile_schema_version_mismatch,test_validate_planfile_wrong_type,test_validate_sprint_valid,test_validate_sprint_missing_required_field,test_validate_sprint_missing_sprint_id,test_validate_yaml_file_planfile,test_validate_yaml_file_invalid_yaml,test_validate_yaml_file_not_found,test_get_current_schema_version
    test_validate_planfile_valid()
    test_validate_planfile_missing_required_field()
    test_validate_planfile_schema_version_mismatch()
    test_validate_planfile_wrong_type()
    test_validate_sprint_valid()
    test_validate_sprint_missing_required_field()
    test_validate_sprint_missing_sprint_id()
    test_validate_yaml_file_planfile()
    test_validate_yaml_file_invalid_yaml()
    test_validate_yaml_file_not_found()
    test_get_current_schema_version()
  tests/test_strategy.py:
    e: test_basic_models,test_yaml_loading
    test_basic_models()
    test_yaml_loading()
  tests/test_testql_integration.py:
    e: _write,test_build_testql_tickets_from_failed_report,test_build_testql_tickets_handles_compact_report_steps_count,test_upsert_testql_tickets_updates_tasks_and_sprint_patterns,test_upsert_testql_tickets_deduplicates_by_external_url,test_sync_testql_tickets_runs_markdown_first,test_sync_testql_tickets_updates_by_external_id,test_sync_testql_tickets_updates_by_url_search,test_resolve_testql_executable_falls_back_to_local_repo,_FakeBackend,_UpdateAwareBackend
    _FakeBackend: __init__(2),create_ticket(1)
    _UpdateAwareBackend: __init__(1),create_ticket(1),update_ticket(1),search_tickets(1)
    _write(path;content)
    test_build_testql_tickets_from_failed_report()
    test_build_testql_tickets_handles_compact_report_steps_count()
    test_upsert_testql_tickets_updates_tasks_and_sprint_patterns(tmp_path)
    test_upsert_testql_tickets_deduplicates_by_external_url(tmp_path)
    test_sync_testql_tickets_runs_markdown_first(tmp_path;monkeypatch)
    test_sync_testql_tickets_updates_by_external_id(tmp_path;monkeypatch)
    test_sync_testql_tickets_updates_by_url_search(tmp_path;monkeypatch)
    test_resolve_testql_executable_falls_back_to_local_repo(tmp_path;monkeypatch)
  tests/test_ticket_files.py:
    e: test_ticket_model_with_files,test_ticket_model_with_file,test_ticket_model_default_files,test_store_filter_by_files,test_store_filter_by_file,test_store_filter_by_files_and_file,test_store_filter_by_files_glob_pattern,test_store_filter_no_files,test_store_filter_multiple_patterns,test_store_matches_files,test_ticket_create_with_files
    test_ticket_model_with_files()
    test_ticket_model_with_file()
    test_ticket_model_default_files()
    test_store_filter_by_files()
    test_store_filter_by_file()
    test_store_filter_by_files_and_file()
    test_store_filter_by_files_glob_pattern()
    test_store_filter_no_files()
    test_store_filter_multiple_patterns()
    test_store_matches_files()
    test_ticket_create_with_files()
  tests/test_ticket_validation.py:
    e: _write,test_validate_planfile_tickets_rule_based_current_and_stale,test_validate_planfile_tickets_line_based_without_scan,test_validate_planfile_tickets_collects_backlog_and_sprint_sections,test_validate_planfile_tickets_filters_specific_ticket_ids,test_validate_planfile_tickets_empty_ticket_ids_returns_all,test_validate_planfile_tickets_nonexistent_ids_returns_empty
    _write(path;content)
    test_validate_planfile_tickets_rule_based_current_and_stale(tmp_path)
    test_validate_planfile_tickets_line_based_without_scan(tmp_path)
    test_validate_planfile_tickets_collects_backlog_and_sprint_sections(tmp_path)
    test_validate_planfile_tickets_filters_specific_ticket_ids(tmp_path)
    test_validate_planfile_tickets_empty_ticket_ids_returns_all(tmp_path)
    test_validate_planfile_tickets_nonexistent_ids_returns_empty(tmp_path)
  tests/test_todo_sync.py:
    e: _write,test_sync_todo_checkboxes_from_planfile_uses_strategy_statuses,test_sync_todo_checkboxes_from_planfile_uses_results_markers,test_sync_todo_checkboxes_from_planfile_respects_disabled_setting
    _write(path;content)
    test_sync_todo_checkboxes_from_planfile_uses_strategy_statuses(tmp_path)
    test_sync_todo_checkboxes_from_planfile_uses_results_markers(tmp_path)
    test_sync_todo_checkboxes_from_planfile_respects_disabled_setting(tmp_path)
```

## Source Map

*Top 5 modules by symbol density — signatures for LLM orientation.*

### `planfile.testql_integration` (`planfile/testql_integration.py`)

```python
def _normalize_ref_text(value)  # CC=2, fan=2
def _normalize_ref_url(value)  # CC=1, fan=2
def _iter_external_refs(ticket)  # CC=4, fan=2
def _collect_ticket_identity_keys(ticket)  # CC=14, fan=9 ⚠
def _collect_external_ref_candidates(ticket, integration)  # CC=9, fan=9
def _extract_result_field(result, field)  # CC=3, fan=5
def _extract_created_ticket_ref(result)  # CC=1, fan=2
def _extract_search_ticket_id(item)  # CC=3, fan=4
def _looks_not_found_error(exc)  # CC=2, fan=2
def _looks_already_exists_error(exc)  # CC=2, fan=2
def _update_existing_ref_entry(refs, integration, ref_id, ref_key, ref_url)  # CC=6, fan=3
def _append_ref_entry(refs, integration, ref_id, ref_key, ref_url)  # CC=4, fan=1
def _update_ticket_integration_fields(ticket, integration, ref_id, ref_key, ref_url)  # CC=4, fan=1
def _attach_external_ref(ticket, integration, ref)  # CC=5, fan=7
def _resolve_update_reference(backend, ticket, integration)  # CC=9, fan=4
def _extract_json_payload(text)  # CC=9, fan=7
def _resolve_scenario_path(scenario_path, project_root)  # CC=2, fan=3
def _resolve_testql_executable(testql_bin, testql_repo_path)  # CC=6, fan=5
def run_testql_validation(scenario_path, project_path)  # CC=6, fan=11
def _collect_step_messages(steps_raw)  # CC=8, fan=5
def _collect_error_messages(errors_raw)  # CC=7, fan=3
def _dedupe_messages(messages)  # CC=3, fan=3
def _collect_failure_messages(report)  # CC=4, fan=6
def _extract_file_from_message(message)  # CC=2, fan=2
def build_testql_tickets(report, scenario_path)  # CC=6, fan=14
def _default_strategy_payload()  # CC=1, fan=0
def _load_or_init_strategy(strategy_file)  # CC=4, fan=5
def _ensure_strategy_lists(strategy)  # CC=7, fan=3
def _build_task_pattern_entry(ticket, ticket_id)  # CC=3, fan=1
def _upsert_single_ticket(ticket, tasks, task_patterns, existing_task_ids, existing_pattern_ids, existing_identity_keys)  # CC=7, fan=9
def upsert_testql_tickets(strategy_path, tickets)  # CC=15, fan=17 ⚠
def _resolve_sync_backend(config, integration)  # CC=2, fan=2
def _sync_ticket_to_backend(ticket, backend, integration)  # CC=6, fan=7
def _sync_tickets_to_integration(tickets, backend, integration)  # CC=5, fan=2
def sync_testql_tickets(tickets)  # CC=9, fan=12
```

### `planfile.ticket_validation` (`planfile/ticket_validation.py`)

```python
def _load_strategy(path)  # CC=3, fan=3
def _normalize_rule(value)  # CC=2, fan=3
def _normalize_rel_path(value, project_root)  # CC=5, fan=6
def _normalize_files(ticket, project_root)  # CC=8, fan=8
def _resolve_ticket_id(ticket, entry_ref)  # CC=4, fan=3
def _iter_tasks_list(items, base_ref)  # CC=4, fan=3
def _iter_tickets_dict(items, base_ref)  # CC=4, fan=3
def _collect_ticket_entries(strategy)  # CC=9, fan=7
def _parse_positive_int(value)  # CC=4, fan=1
def _normalize_ticket_filters(ticket_ids)  # CC=5, fan=4
def _build_issue_indexes(issue_records, project_root)  # CC=14, fan=10 ⚠
def _count_file_lines(abs_path)  # CC=5, fan=4
def _validate_rule_anchor(record, rule_id, files, rule_file_index, scan_available)  # CC=4, fan=1
def _resolve_existing_files(files, project_root)  # CC=3, fan=3
def _validate_line_anchor(record, files, line, project_root, file_line_index, scan_available)  # CC=7, fan=3
def _validate_file_only(record, files, project_root)  # CC=3, fan=2
def _validate_ticket(ticket, entry_ref, project_root, rule_file_index, file_line_index, scan_available)  # CC=8, fan=10
def validate_planfile_tickets(strategy_path, project_path)  # CC=11, fan=12 ⚠
```

### `planfile.ci` (`planfile/ci.py`)

```python
class TestResult:  # Result of running tests.
class BugReport:  # Generated bug report from test failures.
class CIRunner:  # CI/CD runner with automated bug-fix loop and ticket creation
    def __init__(strategy_path, project_path, backends, llx_command, max_iterations, auto_fix, planfile_instance)  # CC=4
    def _extract_json_object(raw_output)  # CC=13 ⚠
    def run_tests()  # CC=6
    def run_code_analysis()  # CC=5
    def generate_bug_report(test_result, metrics)  # CC=10 ⚠
    def create_bug_tickets(bug_report)  # CC=7
    def _resolve_target_file(bug_report)  # CC=6
    def _task_patch_applied(results_payload)  # CC=6
    def _extract_yaml_object(raw_output)  # CC=8
    def auto_fix_bugs(bug_report)  # CC=5
    def check_strategy_completion()  # CC=3
    def run_loop()  # CC=7
    def save_results(results, output_path)  # CC=2
```

### `planfile.executor_standalone` (`planfile/executor_standalone.py`)

```python
def create_openai_client(api_key, model)  # CC=2, fan=4
def create_litellm_client(api_key, model)  # CC=2, fan=3
def execute_strategy(strategy_path, project_path)  # CC=8, fan=2
class TaskResult:  # Result of executing a task.
class LLMClient:  # Simple LLM client interface.
    def __init__(client_func, config)  # CC=2
    def chat(messages, model)  # CC=1
class StrategyExecutor:  # Standalone strategy executor.
    def __init__(client, config)  # CC=2
    def _default_config()  # CC=1
    def execute_strategy(strategy, project_path)  # CC=8
    def _execute_task(task, project_path, dry_run, model_override)  # CC=7
    def _select_model(task)  # CC=7
    def _build_prompt(task, project_path)  # CC=2
    def _get_project_metrics(project_path)  # CC=6
```

### `planfile.todo_sync` (`planfile/todo_sync.py`)

```python
def _load_strategy(path)  # CC=3, fan=3
def _status_done(status)  # CC=2, fan=3
def _get_value(item, key)  # CC=2, fan=3
def _normalize_marker(value)  # CC=2, fan=2
def _collect_markers_from_results(results)  # CC=6, fan=5
def _collect_markers_from_strategy(strategy)  # CC=13, fan=6 ⚠
def _resolve_todo_config(strategy, strategy_path, project_path, enabled_override)  # CC=7, fan=5
def _line_matches_any_marker(body, markers)  # CC=2, fan=2
def sync_todo_checkboxes_from_planfile(strategy_path, project_path)  # CC=14, fan=22 ⚠
```

## Call Graph

*428 nodes · 455 edges · 92 modules · CC̄=2.2*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in Taskfile)* | 0 | 361 | 0 | **361** |
| `_collect_ticket_identity_keys` *(in planfile.testql_integration)* | 14 ⚠ | 2 | 57 | **59** |
| `example_metric_driven_planning` *(in examples.ecosystem.04_llx_integration)* | 9 | 0 | 57 | **57** |
| `example_strategy_generation_with_proxy` *(in examples.ecosystem.03_proxy_routing)* | 8 | 0 | 56 | **56** |
| `create_examples_app` *(in planfile.cli.groups.examples.commands)* | 1 | 1 | 46 | **47** |
| `handle_tool_call` *(in planfile.mcp.server)* | 27 ⚠ | 1 | 42 | **43** |
| `review_strategy_cli` *(in planfile.cli.groups.review.commands)* | 10 ⚠ | 0 | 40 | **40** |
| `main` *(in examples.python-api.04_analytics_simple)* | 1 | 0 | 35 | **35** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/planfile
# nodes: 428 | edges: 455 | modules: 92
# CC̄=2.2

HUBS[20]:
  Taskfile.print
    CC=0  in:361  out:0  total:361
  planfile.testql_integration._collect_ticket_identity_keys
    CC=14  in:2  out:57  total:59
  examples.ecosystem.04_llx_integration.example_metric_driven_planning
    CC=9  in:0  out:57  total:57
  examples.ecosystem.03_proxy_routing.example_strategy_generation_with_proxy
    CC=8  in:0  out:56  total:56
  planfile.cli.groups.examples.commands.create_examples_app
    CC=1  in:1  out:46  total:47
  planfile.mcp.server.handle_tool_call
    CC=27  in:1  out:42  total:43
  planfile.cli.groups.review.commands.review_strategy_cli
    CC=10  in:0  out:40  total:40
  examples.python-api.04_analytics_simple.main
    CC=1  in:0  out:35  total:35
  planfile.analysis.parsers.text_parser.analyze_text
    CC=13  in:4  out:30  total:34
  planfile.testql_integration.upsert_testql_tickets
    CC=15  in:1  out:31  total:32
  planfile.todo_sync.sync_todo_checkboxes_from_planfile
    CC=14  in:0  out:30  total:30
  planfile.testql_integration._collect_external_ref_candidates
    CC=9  in:1  out:29  total:30
  planfile.cli.project_detector.package._detect_from_package_json
    CC=7  in:1  out:28  total:29
  planfile.cli.groups.sync.commands.watch_cmd
    CC=6  in:0  out:29  total:29
  planfile.cli.groups.init.commands.init_strategy_cli
    CC=8  in:0  out:29  total:29
  planfile.cli.groups.health.commands.create_health_app
    CC=1  in:1  out:28  total:29
  planfile.cli.project_detector.fallback._detect_from_structure
    CC=9  in:1  out:27  total:28
  planfile.cli.groups.ticket.commands.ticket_validate
    CC=10  in:0  out:28  total:28
  planfile.cli.groups.backlog.commands.backlog_delete
    CC=11  in:0  out:27  total:27
  planfile.importers.redup_importer._parse_duplicates
    CC=9  in:1  out:26  total:27

MODULES:
  Taskfile  [1 funcs]
    print  CC=0  out:0
  examples.ecosystem.02_mcp_integration  [6 funcs]
    create_mcp_tool_definitions  CC=1  out:7
    example_mcp_session  CC=1  out:26
    run_mcp_tool  CC=4  out:6
    simulate_planfile_apply  CC=5  out:7
    simulate_planfile_generate  CC=9  out:9
    simulate_planfile_review  CC=1  out:2
  examples.ecosystem.03_proxy_routing  [3 funcs]
    create_proxy_config_example  CC=1  out:3
    example_budget_tracking  CC=2  out:19
    example_strategy_generation_with_proxy  CC=8  out:56
  examples.ecosystem.04_llx_integration  [4 funcs]
    analyze_project  CC=4  out:6
    select_model  CC=5  out:2
    create_llx_config_example  CC=1  out:3
    example_metric_driven_planning  CC=9  out:57
  examples.llx_validator  [1 funcs]
    create_validation_script  CC=1  out:4
  examples.python-api.01_basic_usage  [5 funcs]
    example_1_basic_initialization  CC=1  out:5
    example_2_create_ticket  CC=1  out:9
    example_3_quick_ticket  CC=1  out:6
    example_4_list_tickets  CC=3  out:13
    main  CC=1  out:10
  examples.python-api.02_ticket_management  [6 funcs]
    example_bulk_operations  CC=3  out:7
    example_create_tickets  CC=1  out:8
    example_delete_and_move  CC=1  out:4
    example_read_tickets  CC=1  out:12
    example_update_tickets  CC=1  out:8
    main  CC=1  out:11
  examples.python-api.03_integration  [5 funcs]
    example_ci_pipeline_integration  CC=4  out:7
    example_cli_tool_integration  CC=2  out:5
    example_custom_decorator  CC=3  out:17
    example_monitoring_integration  CC=4  out:6
    main  CC=1  out:10
  examples.python-api.03_integration_simple  [1 funcs]
    main  CC=3  out:18
  examples.python-api.04_advanced_filtering  [6 funcs]
    example_basic_filtering  CC=1  out:15
    example_combined_filters  CC=2  out:7
    example_export_filtered  CC=5  out:13
    example_search_by_labels  CC=12  out:10
    example_statistics  CC=8  out:17
    main  CC=1  out:11
  examples.python-api.04_analytics_simple  [1 funcs]
    main  CC=1  out:35
  examples.python-api.05_dsl_usage  [6 funcs]
    example_basic_dsl  CC=1  out:7
    example_batch_operations  CC=4  out:5
    example_parser_only  CC=1  out:8
    example_query_and_export  CC=1  out:5
    example_sprint_management  CC=1  out:5
    example_validation_sync  CC=1  out:7
  examples.rest-api.03_python_client  [5 funcs]
    example_basic_operations  CC=1  out:10
    example_bulk_operations  CC=2  out:12
    example_error_handling  CC=3  out:7
    example_workflow  CC=1  out:12
    main  CC=4  out:21
  examples.rest-api.04_dsl_usage  [7 funcs]
    example_dsl_command  CC=1  out:3
    example_dsl_create_ticket  CC=1  out:3
    example_dsl_help  CC=1  out:3
    example_dsl_sprint  CC=1  out:6
    example_dsl_update_ticket  CC=1  out:3
    example_dsl_validate_sync  CC=1  out:6
    example_yaml_operations  CC=1  out:6
  examples.rest-api.04_javascript_client  [13 funcs]
    BASE_URL  CC=5  out:17
    client  CC=2  out:10
    createTicket  CC=1  out:1
    fetched  CC=1  out:1
    getTicket  CC=1  out:1
    health  CC=1  out:1
    listTickets  CC=1  out:1
    moveTicket  CC=1  out:1
    request  CC=5  out:8
    ticket  CC=1  out:1
  examples.rest-api.06_websocket  [6 funcs]
    example_websocket_basic  CC=1  out:6
    example_websocket_batch  CC=2  out:7
    example_websocket_error_handling  CC=3  out:8
    example_websocket_interactive  CC=2  out:9
    example_websocket_raw_text  CC=1  out:7
    main  CC=1  out:3
  planfile  [1 funcs]
    quick_ticket  CC=1  out:4
  planfile.analysis.external_tools  [3 funcs]
    run_code2llm  CC=3  out:10
    run_redup  CC=3  out:10
    run_vallm  CC=3  out:10
  planfile.analysis.file_analyzer  [7 funcs]
    _analyze_json  CC=1  out:1
    _analyze_text  CC=1  out:1
    _analyze_toon  CC=1  out:1
    _analyze_yaml  CC=1  out:1
    _extract_from_json_structure  CC=1  out:1
    _extract_from_yaml_structure  CC=1  out:1
    analyze_file  CC=4  out:5
  planfile.analysis.generator  [10 funcs]
    _extract_key_metrics  CC=1  out:1
    _generate_goal  CC=1  out:1
    _generate_goals  CC=1  out:1
    _generate_quality_gates  CC=1  out:1
    _generate_risks  CC=1  out:1
    _generate_success_criteria  CC=1  out:1
    _generate_target_metrics  CC=1  out:1
    _generate_tasks  CC=1  out:1
    _parse_effort  CC=1  out:1
    generate_with_external_tools  CC=1  out:10
  planfile.analysis.generators.metrics_extractor  [6 funcs]
    _extract_cc_metrics  CC=7  out:5
    _extract_coverage_metrics  CC=4  out:1
    _extract_critical_metrics  CC=7  out:4
    _extract_duplication_metrics  CC=6  out:3
    _extract_validation_metrics  CC=9  out:6
    extract_key_metrics  CC=2  out:6
  planfile.analysis.parsers.json_parser  [1 funcs]
    analyze_json  CC=2  out:9
  planfile.analysis.parsers.text_parser  [1 funcs]
    analyze_text  CC=13  out:30
  planfile.analysis.parsers.toon_parser  [3 funcs]
    _determine_section  CC=11  out:7
    _parse_toon_sections  CC=4  out:3
    analyze_toon  CC=5  out:15
  planfile.analysis.parsers.yaml_parser  [7 funcs]
    _create_issue_from_value  CC=1  out:1
    _is_issue_content  CC=4  out:4
    _process_yaml_dict  CC=4  out:4
    _process_yaml_list  CC=2  out:3
    _process_yaml_value  CC=4  out:7
    analyze_yaml  CC=4  out:20
    extract_from_yaml_structure  CC=5  out:8
  planfile.api.server  [12 funcs]
    create_sprint  CC=4  out:13
    create_ticket  CC=1  out:5
    delete_ticket  CC=2  out:4
    done_ticket  CC=2  out:5
    get_ticket  CC=2  out:5
    get_yaml  CC=3  out:7
    list_sprints  CC=3  out:7
    list_tickets  CC=5  out:8
    move_ticket  CC=2  out:5
    patch_yaml  CC=6  out:11
  planfile.ci  [2 funcs]
    __init__  CC=4  out:5
    check_strategy_completion  CC=3  out:9
  planfile.cli.core.console  [1 funcs]
    print_warning  CC=1  out:1
  planfile.cli.core.errors  [2 funcs]
    exit_with_error  CC=1  out:2
    handle_exception  CC=2  out:3
  planfile.cli.core.registry  [2 funcs]
    register_simple_command  CC=2  out:1
    register_typer_group  CC=1  out:2
  planfile.cli.extra_commands  [1 funcs]
    add_extra_commands  CC=1  out:4
  planfile.cli.groups.apply  [1 funcs]
    register_apply_commands  CC=1  out:1
  planfile.cli.groups.apply.commands  [2 funcs]
    apply_strategy_cli  CC=6  out:20
    execute_apply_strategy  CC=1  out:5
  planfile.cli.groups.apply.utils  [5 funcs]
    get_backend  CC=7  out:16
    load_and_validate_strategy  CC=2  out:4
    load_backend_config  CC=5  out:11
    parse_sprint_filter  CC=4  out:5
    select_backend  CC=2  out:3
  planfile.cli.groups.auto.commands  [2 funcs]
    _initialize_backends  CC=3  out:4
    get_backend  CC=4  out:13
  planfile.cli.groups.backlog.commands  [10 funcs]
    _collect_backlog_to_delete  CC=6  out:5
    _collect_targets_to_delete  CC=4  out:5
    _get_planfile_yaml_path  CC=3  out:4
    _load_planfile_yaml  CC=2  out:6
    _matches_files  CC=5  out:2
    _print_deletion_preview  CC=5  out:8
    _save_planfile_yaml  CC=1  out:3
    backlog_delete  CC=11  out:27
    backlog_list  CC=10  out:14
    create_backlog_table  CC=3  out:16
  planfile.cli.groups.dsl.commands  [3 funcs]
    _interactive_shell  CC=7  out:8
    _run_single  CC=8  out:11
    dsl_run  CC=2  out:7
  planfile.cli.groups.examples  [1 funcs]
    register_examples_commands  CC=1  out:1
  planfile.cli.groups.examples.commands  [2 funcs]
    _discover_examples  CC=13  out:18
    create_examples_app  CC=1  out:46
  planfile.cli.groups.generate.commands  [1 funcs]
    generate_strategy_cli  CC=5  out:20
  planfile.cli.groups.health  [1 funcs]
    register_health_commands  CC=1  out:1
  planfile.cli.groups.health.commands  [1 funcs]
    create_health_app  CC=1  out:28
  planfile.cli.groups.init  [1 funcs]
    register_init_commands  CC=1  out:1
  planfile.cli.groups.init.commands  [7 funcs]
    _ask  CC=7  out:3
    _ask_list  CC=4  out:6
    _choice  CC=11  out:12
    _collect_custom_sprints  CC=2  out:8
    _collect_preset_sprints  CC=5  out:16
    _collect_sprint_data  CC=2  out:2
    init_strategy_cli  CC=8  out:29
  planfile.cli.groups.query.commands  [7 funcs]
    _export_to_csv  CC=6  out:12
    calculate_strategy_stats  CC=7  out:14
    compare_cmd  CC=7  out:18
    compare_strategies  CC=10  out:22
    export_cmd  CC=5  out:15
    merge_cmd  CC=3  out:10
    stats_cmd  CC=5  out:24
  planfile.cli.groups.review  [1 funcs]
    register_review_commands  CC=1  out:1
  planfile.cli.groups.review.commands  [1 funcs]
    review_strategy_cli  CC=10  out:40
  planfile.cli.groups.review.utils  [2 funcs]
    _load_and_validate_strategy  CC=2  out:3
    _load_backend_config  CC=6  out:13
  planfile.cli.groups.sync.commands  [10 funcs]
    _resolve_watch_integrations  CC=4  out:5
    _run_sync_once  CC=3  out:2
    all_cmd  CC=2  out:11
    github_cmd  CC=1  out:4
    gitlab_cmd  CC=1  out:4
    handle_no_integrations  CC=1  out:2
    jira_cmd  CC=1  out:4
    markdown_cmd  CC=1  out:4
    sync_all_integrations  CC=3  out:5
    watch_cmd  CC=6  out:29
  planfile.cli.groups.sync.core  [11 funcs]
    _collect_tickets_from_backlog  CC=4  out:4
    _collect_tickets_from_section  CC=3  out:5
    _collect_tickets_from_sprint  CC=4  out:4
    _execute_sync_with_progress  CC=3  out:9
    _initialize_backend  CC=6  out:9
    _load_tickets_for_sync  CC=3  out:9
    _load_tickets_v1_format  CC=2  out:4
    _process_planfile_v1  CC=9  out:11
    _ticket_matches_integration  CC=3  out:2
    _ticket_matches_integration_v1  CC=2  out:2
  planfile.cli.groups.ticket.commands  [10 funcs]
    _apply_label_changes  CC=6  out:5
    _auto_sync  CC=6  out:11
    _display_tickets  CC=6  out:9
    _execute_bulk_updates  CC=4  out:6
    _load_issue_records_from_file  CC=12  out:14
    create_ticket_table  CC=5  out:14
    load_import_tickets  CC=5  out:6
    ticket_import  CC=1  out:8
    ticket_list  CC=6  out:10
    ticket_validate  CC=10  out:28
  planfile.cli.groups.validate.commands  [2 funcs]
    validate_schema_cli  CC=9  out:16
    validate_strategy_cli  CC=9  out:22
  planfile.cli.project_detector.fallback  [1 funcs]
    _detect_from_structure  CC=9  out:27
  planfile.cli.project_detector.gates  [13 funcs]
    _detect_ci_gates  CC=3  out:3
    _detect_doc_gates  CC=3  out:3
    _detect_docker_gates  CC=3  out:3
    _detect_quality_gates  CC=3  out:7
    _detect_quality_tool_gates  CC=3  out:2
    _detect_security_gates  CC=3  out:2
    _detect_test_gates  CC=8  out:10
    _find_quality_tools  CC=4  out:6
    _find_security_tools  CC=7  out:6
    _has_bandit_config  CC=5  out:2
  planfile.cli.project_detector.git  [1 funcs]
    _detect_git_authors  CC=4  out:5
  planfile.cli.project_detector.inference  [3 funcs]
    _infer_domain  CC=4  out:4
    _infer_node_project_type  CC=9  out:5
    _infer_python_project_type  CC=11  out:11
  planfile.cli.project_detector.license  [1 funcs]
    _detect_license  CC=9  out:2
  planfile.cli.project_detector.main  [5 funcs]
    _build_detected_dict  CC=9  out:3
    _determine_source  CC=4  out:3
    _quality_gates_to_dict  CC=2  out:0
    detect_project  CC=4  out:5
    get_detected_values  CC=1  out:2
  planfile.cli.project_detector.model_tier  [4 funcs]
    _detect_model_tier  CC=3  out:3
    _tier_from_config_files  CC=9  out:3
    _tier_from_env_files  CC=8  out:2
    _tier_from_env_vars  CC=4  out:1
  planfile.cli.project_detector.package  [1 funcs]
    _detect_from_package_json  CC=7  out:28
  planfile.cli.project_detector.pyproject  [9 funcs]
    _detect_from_pyproject  CC=4  out:6
    _get_project_dependencies  CC=6  out:2
    _import_toml_loader  CC=3  out:0
    _load_pyproject_data  CC=3  out:3
    _populate_inferred_project_details  CC=3  out:6
    _populate_poetry_metadata  CC=2  out:5
    _populate_project_from_data  CC=5  out:2
    _populate_project_metadata  CC=8  out:13
    _populate_readme_and_repository_details  CC=4  out:10
  planfile.cli.project_detector.readme  [5 funcs]
    _extract_description  CC=6  out:6
    _extract_goal  CC=8  out:11
    _find_readme_content  CC=4  out:5
    _find_readme_description  CC=1  out:1
    _find_readme_goal  CC=1  out:1
  planfile.cli.project_detector.structure  [4 funcs]
    _analyze_directory_structure  CC=1  out:3
    _find_src_dirs  CC=12  out:11
    _has_tests  CC=2  out:2
    _suggest_sprints  CC=6  out:8
  planfile.core.models.strategy  [2 funcs]
    export  CC=5  out:12
    to_yaml  CC=2  out:5
  planfile.core.schema  [1 funcs]
    validate_yaml_file  CC=5  out:5
  planfile.dsl.executor  [2 funcs]
    _exec_sync  CC=6  out:20
    _exec_validate  CC=1  out:8
  planfile.examples  [5 funcs]
    example_create_strategy  CC=1  out:1
    example_programmatic_strategy  CC=1  out:11
    example_run_strategy  CC=1  out:1
    example_validate_strategy  CC=2  out:5
    example_verify_strategy  CC=2  out:4
  planfile.importers  [1 funcs]
    import_from_source  CC=8  out:11
  planfile.importers.code2llm_importer  [6 funcs]
    _handle_in_next  CC=13  out:14
    parse  CC=3  out:4
    _evolution_item_to_ticket  CC=6  out:11
    _parse_evolution  CC=1  out:2
    _parse_health  CC=9  out:8
    import_code2llm  CC=3  out:4
  planfile.importers.common  [2 funcs]
    load_structured_tickets  CC=6  out:10
    normalize_ticket_dict  CC=5  out:8
  planfile.importers.json_importer  [1 funcs]
    import_json  CC=1  out:1
  planfile.importers.redup_importer  [5 funcs]
    _create_refactor_ticket  CC=9  out:13
    _parse_duplicates  CC=9  out:26
    _parse_refactor  CC=11  out:15
    _parse_toon_format  CC=9  out:22
    import_redup  CC=3  out:7
  planfile.importers.vallm_importer  [3 funcs]
    _parse_issue_entry  CC=3  out:5
    _auto_labels  CC=3  out:3
    import_vallm  CC=1  out:4
  planfile.importers.yaml_importer  [1 funcs]
    import_yaml  CC=1  out:1
  planfile.llm.client  [1 funcs]
    call_llm  CC=4  out:10
  planfile.llm.generator  [6 funcs]
    _auto_select_model  CC=4  out:4
    _basic_metrics  CC=8  out:6
    _collect_metrics  CC=2  out:3
    _fix_yaml_formatting  CC=6  out:7
    _parse_strategy_response  CC=3  out:7
    generate_strategy  CC=3  out:7
  planfile.llm.prompts  [1 funcs]
    build_strategy_prompt  CC=5  out:9
  planfile.loaders.cli_loader  [8 funcs]
    _md_header  CC=1  out:3
    _md_summary  CC=2  out:3
    _md_tasks  CC=7  out:6
    export_results_to_markdown  CC=1  out:15
    load_from_json  CC=2  out:5
    load_strategy_from_json  CC=1  out:2
    save_strategy_to_json  CC=1  out:2
    save_to_json  CC=1  out:4
  planfile.loaders.yaml_loader  [15 funcs]
    _check_required_keys  CC=3  out:1
    _format_validation_error  CC=5  out:7
    _transform_goal  CC=4  out:3
    _transform_sprints  CC=4  out:0
    _transform_task_patterns  CC=6  out:3
    _validate_gates  CC=6  out:4
    _validate_sprints  CC=6  out:6
    _validate_task_patterns  CC=7  out:5
    load_strategy_yaml  CC=2  out:6
    load_tasks_yaml  CC=5  out:6
  planfile.mcp.server  [4 funcs]
    _read_jsonrpc  CC=4  out:2
    _write_jsonrpc  CC=1  out:3
    handle_tool_call  CC=27  out:42
    main  CC=8  out:12
  planfile.runner  [7 funcs]
    _get_project_hash  CC=5  out:11
    analyze_project_metrics  CC=12  out:25
    apply_strategy_to_tickets  CC=8  out:8
    load_valid_strategy  CC=3  out:7
    review_strategy  CC=14  out:9
    run_strategy  CC=8  out:23
    verify_strategy_post_execution  CC=12  out:12
  planfile.server_common  [1 funcs]
    get_planfile  CC=2  out:1
  planfile.sync.mock  [4 funcs]
    _create_ticket  CC=4  out:7
    _list_tickets  CC=11  out:13
    _search_tickets  CC=5  out:14
    _update_ticket  CC=8  out:5
  planfile.sync.operations  [15 funcs]
    _create_new_ticket  CC=4  out:8
    _extract_ticket_data  CC=9  out:16
    _fetch_external_tickets  CC=3  out:4
    _import_new_ticket  CC=2  out:5
    _is_permission_error  CC=3  out:4
    _load_sprint_and_backlog  CC=5  out:4
    _print_dry_run_action  CC=3  out:4
    _print_permission_error  CC=1  out:9
    _process_external_ticket  CC=4  out:6
    _save_import_results  CC=5  out:6
  planfile.sync.state  [1 funcs]
    save_sync  CC=2  out:9
  planfile.sync.utils  [1 funcs]
    save_v1_format  CC=1  out:2
  planfile.testql_integration  [34 funcs]
    _append_ref_entry  CC=4  out:1
    _attach_external_ref  CC=5  out:10
    _build_task_pattern_entry  CC=3  out:4
    _collect_error_messages  CC=7  out:5
    _collect_external_ref_candidates  CC=9  out:29
    _collect_failure_messages  CC=4  out:8
    _collect_step_messages  CC=8  out:10
    _collect_ticket_identity_keys  CC=14  out:57
    _dedupe_messages  CC=3  out:3
    _default_strategy_payload  CC=1  out:0
  planfile.ticket_validation  [16 funcs]
    _build_issue_indexes  CC=14  out:23
    _collect_ticket_entries  CC=9  out:25
    _count_file_lines  CC=5  out:4
    _load_strategy  CC=3  out:3
    _normalize_files  CC=8  out:11
    _normalize_rel_path  CC=5  out:10
    _normalize_rule  CC=2  out:3
    _normalize_ticket_filters  CC=5  out:5
    _parse_positive_int  CC=4  out:1
    _resolve_existing_files  CC=3  out:3
  planfile.todo_sync  [8 funcs]
    _collect_markers_from_results  CC=6  out:6
    _collect_markers_from_strategy  CC=13  out:17
    _get_value  CC=2  out:3
    _load_strategy  CC=3  out:3
    _normalize_marker  CC=2  out:2
    _resolve_todo_config  CC=7  out:10
    _status_done  CC=2  out:3
    sync_todo_checkboxes_from_planfile  CC=14  out:30
  planfile.utils.metrics  [4 funcs]
    _check_project_files  CC=2  out:1
    _collect_git_metrics  CC=8  out:15
    _count_files_by_language  CC=6  out:11
    analyze_project_metrics  CC=3  out:10
  project.map.toon  [9 funcs]
    create_strategy_command  CC=0  out:0
    generate_goal  CC=0  out:0
    generate_goals  CC=0  out:0
    generate_quality_gates  CC=0  out:0
    generate_risks  CC=0  out:0
    generate_success_criteria  CC=0  out:0
    generate_target_metrics  CC=0  out:0
    generate_tasks  CC=0  out:0
    parse_effort  CC=0  out:0
  scripts.run_examples  [1 funcs]
    print_error  CC=0  out:0

EDGES:
  examples.llx_validator.create_validation_script → Taskfile.print
  examples.rest-api.04_javascript_client.BASE_URL → examples.rest-api.04_javascript_client.PlanfileClient.request
  examples.rest-api.04_javascript_client.PlanfileClient.health → examples.rest-api.04_javascript_client.PlanfileClient.createTicket
  examples.rest-api.04_javascript_client.PlanfileClient.listTickets → examples.rest-api.04_javascript_client.PlanfileClient.request
  examples.rest-api.04_javascript_client.PlanfileClient.createTicket → examples.rest-api.04_javascript_client.PlanfileClient.request
  examples.rest-api.04_javascript_client.PlanfileClient.getTicket → examples.rest-api.04_javascript_client.PlanfileClient.request
  examples.rest-api.04_javascript_client.PlanfileClient.updateTicket → examples.rest-api.04_javascript_client.PlanfileClient.request
  examples.rest-api.04_javascript_client.PlanfileClient.moveTicket → examples.rest-api.04_javascript_client.PlanfileClient.request
  examples.rest-api.04_javascript_client.PlanfileClient.client → examples.rest-api.04_javascript_client.PlanfileClient.health
  examples.rest-api.04_javascript_client.PlanfileClient.client → examples.rest-api.04_javascript_client.PlanfileClient.createTicket
  examples.rest-api.04_javascript_client.PlanfileClient.client → examples.rest-api.04_javascript_client.PlanfileClient.getTicket
  examples.rest-api.04_javascript_client.PlanfileClient.client → examples.rest-api.04_javascript_client.PlanfileClient.updateTicket
  examples.rest-api.04_javascript_client.PlanfileClient.client → examples.rest-api.04_javascript_client.PlanfileClient.listTickets
  examples.rest-api.04_javascript_client.PlanfileClient.client → examples.rest-api.04_javascript_client.PlanfileClient.moveTicket
  examples.rest-api.04_javascript_client.PlanfileClient.ticket → examples.rest-api.04_javascript_client.PlanfileClient.createTicket
  examples.rest-api.04_javascript_client.PlanfileClient.fetched → examples.rest-api.04_javascript_client.PlanfileClient.updateTicket
  examples.rest-api.04_javascript_client.PlanfileClient.updated → examples.rest-api.04_javascript_client.PlanfileClient.updateTicket
  examples.rest-api.04_javascript_client.PlanfileClient.tickets → examples.rest-api.04_javascript_client.PlanfileClient.listTickets
  examples.rest-api.03_python_client.example_basic_operations → Taskfile.print
  examples.rest-api.03_python_client.example_bulk_operations → Taskfile.print
  examples.rest-api.03_python_client.example_workflow → Taskfile.print
  examples.rest-api.03_python_client.example_error_handling → Taskfile.print
  examples.rest-api.03_python_client.main → Taskfile.print
  examples.rest-api.03_python_client.main → examples.rest-api.03_python_client.example_basic_operations
  examples.rest-api.03_python_client.main → examples.rest-api.03_python_client.example_bulk_operations
  examples.rest-api.03_python_client.main → examples.rest-api.03_python_client.example_workflow
  examples.ecosystem.02_mcp_integration.run_mcp_tool → Taskfile.print
  examples.ecosystem.02_mcp_integration.run_mcp_tool → examples.ecosystem.02_mcp_integration.simulate_planfile_generate
  examples.ecosystem.02_mcp_integration.run_mcp_tool → examples.ecosystem.02_mcp_integration.simulate_planfile_apply
  examples.ecosystem.02_mcp_integration.run_mcp_tool → examples.ecosystem.02_mcp_integration.simulate_planfile_review
  examples.ecosystem.02_mcp_integration.simulate_planfile_generate → Taskfile.print
  examples.ecosystem.02_mcp_integration.simulate_planfile_apply → Taskfile.print
  examples.ecosystem.02_mcp_integration.example_mcp_session → Taskfile.print
  examples.ecosystem.02_mcp_integration.example_mcp_session → examples.ecosystem.02_mcp_integration.run_mcp_tool
  examples.ecosystem.02_mcp_integration.create_mcp_tool_definitions → Taskfile.print
  examples.ecosystem.04_llx_integration.LLXIntegration.analyze_project → Taskfile.print
  examples.ecosystem.04_llx_integration.example_metric_driven_planning → Taskfile.print
  examples.ecosystem.04_llx_integration.create_llx_config_example → Taskfile.print
  examples.ecosystem.03_proxy_routing.example_strategy_generation_with_proxy → Taskfile.print
  examples.ecosystem.03_proxy_routing.create_proxy_config_example → Taskfile.print
  examples.ecosystem.03_proxy_routing.example_budget_tracking → Taskfile.print
  examples.python-api.04_advanced_filtering.example_basic_filtering → Taskfile.print
  examples.python-api.04_advanced_filtering.example_combined_filters → Taskfile.print
  examples.python-api.04_advanced_filtering.example_search_by_labels → Taskfile.print
  examples.python-api.04_advanced_filtering.example_export_filtered → Taskfile.print
  examples.python-api.04_advanced_filtering.example_statistics → Taskfile.print
  examples.python-api.04_advanced_filtering.main → Taskfile.print
  examples.python-api.04_advanced_filtering.main → examples.python-api.04_advanced_filtering.example_basic_filtering
  examples.python-api.04_advanced_filtering.main → examples.python-api.04_advanced_filtering.example_combined_filters
  examples.python-api.04_advanced_filtering.main → examples.python-api.04_advanced_filtering.example_search_by_labels
```

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Integration (1)

**`Auto-generated from Python Tests`**

### Unit (1)

**`Library Unit Tests`**

## Intent

SDLC automation platform - strategic project management with CI/CD integration and automated bug-fix loops
