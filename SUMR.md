# Planfile

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Dependencies](#dependencies)
- [Source Map](#source-map)
- [Call Graph](#call-graph)
- [Test Contracts](#test-contracts)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `planfile`
- **version**: `0.1.86`
- **python_requires**: `>=3.10`
- **license**: {'text': 'Apache-2.0'}
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, testql(2), app.doql.less, goal.yaml, Dockerfile, docker-compose.yml, src(11 mod), project/(6 analysis files)

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

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

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

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 293f 338177L | python:149,yaml:88,shell:39,json:9,yml:2,txt:2,toml:1,javascript:1 | 2026-05-03
# CC̄=2.2 | critical:4/1375 | dups:0 | cycles:0

HEALTH[4]:
  🟡 CC    upsert_testql_tickets CC=15 (limit:15)
  🟡 CC    ticket_bulk_update CC=21 (limit:15)
  🟡 CC    handle_tool_call CC=27 (limit:15)
  🟡 CC    _extract_modifiers CC=15 (limit:15)

REFACTOR[1]:
  1. split 4 high-CC methods  (CC>15)

PIPELINES[430]:
  [1] Src [validate_strategy]: validate_strategy
      PURITY: 100% pure
  [2] Src [analyze_generated_code]: analyze_generated_code
      PURITY: 100% pure
  [3] Src [_is_llx_available]: _is_llx_available
      PURITY: 100% pure
  [4] Src [_parse_llx_analysis]: _parse_llx_analysis
      PURITY: 100% pure
  [5] Src [_basic_code_analysis]: _basic_code_analysis
      PURITY: 100% pure

LAYERS:
  planfile/                       CC̄=4.1    ←in:53  →out:34  !! split
  │ !! testql_integration         711L  0C   35m  CC=15     ←1
  │ !! commands                   519L  0C   23m  CC=21     ←0
  │ ci                         472L  3C   13m  CC=13     ←0
  │ runner                     418L  0C    7m  CC=14     ←4
  │ ticket_validation          362L  0C   18m  CC=14     ←2
  │ generator                  347L  1C   24m  CC=14     ←0
  │ executor_standalone        338L  3C   12m  CC=8      ←0
  │ executor                   336L  2C   21m  CC=7      ←0
  │ yaml_loader                331L  0C   15m  CC=7      ←7
  │ server                     331L  7C   21m  CC=6      ←0
  │ !! server                     321L  0C    4m  CC=27     ←0
  │ jira                       284L  1C   13m  CC=8      ←0
  │ strategy                   273L  6C   14m  CC=12     ←0
  │ external_tools             268L  2C   12m  CC=12     ←0
  │ operations                 260L  0C   15m  CC=10     ←1
  │ core                       256L  0C   11m  CC=9      ←3
  │ commands                   244L  0C    8m  CC=10     ←0
  │ github                     238L  1C   13m  CC=8      ←0
  │ base                       236L  4C   21m  CC=4      ←0
  │ commands                   235L  0C    8m  CC=10     ←0
  │ gitlab                     227L  1C   12m  CC=9      ←0
  │ metrics                    227L  0C    5m  CC=8      ←0
  │ redup_importer             221L  0C    5m  CC=11     ←1
  │ commands                   218L  0C   11m  CC=11     ←0
  │ generic                    216L  1C   10m  CC=6      ←0
  │ sprint_generator           206L  1C   10m  CC=9      ←0
  │ config                     206L  1C   14m  CC=10     ←0
  │ !! parser                     205L  2C    6m  CC=15     ←0
  │ commands                   197L  0C    3m  CC=13     ←1
  │ cli_loader                 194L  0C   10m  CC=7      ←0
  │ commands                   194L  0C   12m  CC=11     ←0
  │ __init__                   192L  1C   11m  CC=11     ←10
  │ toon_parser                189L  0C    7m  CC=11     ←2
  │ todo_sync                  184L  0C    9m  CC=14     ←0
  │ commands                   174L  0C   12m  CC=6      ←0
  │ gates                      170L  0C   13m  CC=8      ←3
  │ mock                       161L  1C    6m  CC=11     ←0
  │ commands                   160L  0C    3m  CC=9      ←0
  │ store                      151L  1C   13m  CC=6      ←0
  │ generator                  145L  0C    6m  CC=8      ←1
  │ examples                   139L  0C    5m  CC=2      ←0
  │ commands                   132L  0C    2m  CC=14     ←0
  │ code2llm_importer          129L  1C    9m  CC=13     ←1
  │ commands                   128L  0C    5m  CC=13     ←0
  │ file_analyzer              127L  1C   10m  CC=9      ←0
  │ backend                    124L  1C    8m  CC=5      ←0
  │ yaml_parser                123L  0C    7m  CC=5      ←2
  │ commands                   119L  0C    4m  CC=6      ←0
  │ text_parser                118L  0C    1m  CC=13     ←3
  │ pyproject                  117L  0C    9m  CC=8      ←1
  │ schema                     114L  1C    4m  CC=8      ←1
  │ priorities                 111L  0C    3m  CC=4      ←0
  │ tickets                    110L  1C    6m  CC=12     ←0
  │ utils                      108L  0C    5m  CC=7      ←1
  │ __init__                   104L  1C    5m  CC=3      ←0
  │ commands                   100L  0C    1m  CC=10     ←0
  │ main                       100L  0C    5m  CC=9      ←1
  │ vallm_importer              96L  1C   10m  CC=4      ←1
  │ store_tickets               86L  1C    8m  CC=8      ←0
  │ utils                       86L  0C    3m  CC=7      ←1
  │ inference                   80L  0C    3m  CC=11     ←2
  │ commands                    78L  0C    1m  CC=1      ←1
  │ adapters                    75L  6C    5m  CC=1      ←0
  │ package                     73L  0C    1m  CC=7      ←1
  │ structure                   70L  0C    4m  CC=12     ←3
  │ registry                    67L  1C    5m  CC=2      ←5
  │ __init__                    67L  0C    0m  CC=0.0    ←0
  │ fallback                    66L  0C    1m  CC=9      ←1
  │ readme                      66L  0C    5m  CC=8      ←3
  │ commands                    63L  0C    3m  CC=2      ←0
  │ prompts                     63L  0C    1m  CC=5      ←1
  │ client                      63L  0C    1m  CC=4      ←1
  │ model_tier                  60L  0C    4m  CC=9      ←3
  │ ticket                      49L  2C    0m  CC=0.0    ←0
  │ base                        47L  3C    0m  CC=0.0    ←0
  │ state                       46L  1C    5m  CC=3      ←0
  │ metrics_extractor           44L  0C    6m  CC=9      ←1
  │ models                      39L  3C    0m  CC=0.0    ←0
  │ __init__                    38L  0C    1m  CC=1      ←0
  │ git                         36L  0C    1m  CC=4      ←3
  │ common                      35L  0C    2m  CC=6      ←2
  │ __init__                    35L  0C    0m  CC=0.0    ←0
  │ base                        34L  2C    0m  CC=0.0    ←0
  │ __init__                    32L  0C    0m  CC=0.0    ←0
  │ json_parser                 31L  0C    1m  CC=2      ←1
  │ store_files                 31L  1C    3m  CC=6      ←0
  │ progress                    31L  0C    2m  CC=1      ←0
  │ console                     31L  0C    5m  CC=1      ←1
  │ license                     30L  0C    1m  CC=9      ←3
  │ __init__                    29L  0C    2m  CC=8      ←1
  │ auto_loop                   26L  0C    1m  CC=1      ←0
  │ __init__                    25L  0C    0m  CC=0.0    ←0
  │ files                       24L  1C    1m  CC=3      ←0
  │ errors                      24L  0C    3m  CC=2      ←0
  │ __init__                    23L  0C    0m  CC=0.0    ←0
  │ __init__                    23L  0C    0m  CC=0.0    ←0
  │ __init__                    22L  0C    1m  CC=1      ←0
  │ models                      21L  0C    0m  CC=0.0    ←0
  │ __init__                    21L  0C    0m  CC=0.0    ←0
  │ extra_commands              20L  0C    1m  CC=1      ←0
  │ __init__                    19L  0C    1m  CC=1      ←0
  │ __init__                    18L  0C    1m  CC=1      ←0
  │ __init__                    18L  0C    1m  CC=1      ←0
  │ __init__                    18L  0C    1m  CC=1      ←0
  │ __init__                    15L  0C    1m  CC=1      ←0
  │ server_common               14L  0C    1m  CC=2      ←2
  │ yaml_importer               14L  0C    1m  CC=1      ←1
  │ json_importer               14L  0C    1m  CC=1      ←1
  │ __init__                    12L  0C    0m  CC=0.0    ←0
  │ utils                       11L  0C    1m  CC=1      ←1
  │ __init__                    11L  0C    1m  CC=1      ←0
  │ __init__                    11L  0C    1m  CC=1      ←0
  │ __init__                    11L  0C    1m  CC=1      ←0
  │ __init__                    11L  0C    1m  CC=1      ←0
  │ __init__                    11L  0C    1m  CC=1      ←0
  │ execution                    6L  0C    0m  CC=0.0    ←0
  │ constants                    5L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ __main__                     4L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ base                         1L  0C    0m  CC=0.0    ←0
  │ gitlab                       1L  0C    0m  CC=0.0    ←0
  │ jira                         1L  0C    0m  CC=0.0    ←0
  │ github                       1L  0C    0m  CC=0.0    ←0
  │ generic                      1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │
  examples/                       CC̄=1.9    ←in:0  →out:1
  │ !! ci-strategy.yaml          3100L  0C    0m  CC=0.0    ←0
  │ !! final-strategy.yaml       1197L  0C    0m  CC=0.0    ←0
  │ !! 04_llx_integration         503L  2C    9m  CC=12     ←1
  │ 02_mcp_integration         381L  0C    6m  CC=9      ←0
  │ 03_proxy_routing           368L  1C    7m  CC=8      ←0
  │ 01_full_workflow.sh        352L  4C   12m  CC=0.0    ←0
  │ current.yaml               322L  0C    0m  CC=0.0    ←0
  │ backlog.yaml               294L  0C    0m  CC=0.0    ←0
  │ ecommerce-mvp.yaml         290L  0C    0m  CC=0.0    ←0
  │ quick-start.yaml           278L  0C    0m  CC=0.0    ←0
  │ test_interactive_expect.sh   278L  0C    0m  CC=0.0    ←0
  │ test_planfile_generation.sh   277L  4C    7m  CC=0.0    ←0
  │ onboarding.yaml            275L  0C    0m  CC=0.0    ←0
  │ 03_python_client           250L  1C   14m  CC=4      ←0
  │ verify_planfile.sh         245L  0C    2m  CC=0.0    ←0
  │ microservices-migration.yaml   228L  0C    0m  CC=0.0    ←0
  │ security-hardening.yaml    225L  0C    0m  CC=0.0    ←0
  │ ml-pipeline-optimization.yaml   225L  0C    0m  CC=0.0    ←0
  │ common-tasks.yaml          218L  0C    0m  CC=0.0    ←0
  │ run_all_tests.sh           203L  0C    2m  CC=0.0    ←0
  │ llx_validator              185L  1C    7m  CC=4      ←0
  │ llm-config.yaml            181L  0C    0m  CC=0.0    ←0
  │ 02_ticket_management       172L  0C    6m  CC=3      ←0
  │ PROPOSED_API_IMPROVEMENTS   168L  1C    3m  CC=13     ←0
  │ run.sh                     166L  0C    1m  CC=0.0    ←0
  │ 04_advanced_filtering      161L  0C    6m  CC=12     ←0
  │ 03_integration             159L  0C    5m  CC=4      ←0
  │ test_readme_examples.sh    158L  1C    3m  CC=0.0    ←0
  │ 04_javascript_client.js    152L  1C   18m  CC=5      ←0
  │ backlog.yaml               139L  0C    0m  CC=0.0    ←0
  │ run.sh                     129L  0C    0m  CC=0.0    ←0
  │ tickets.planfile.yaml      128L  0C    0m  CC=0.0    ←0
  │ run.sh                     128L  0C    0m  CC=0.0    ←0
  │ 06_websocket               117L  0C    6m  CC=3      ←0
  │ 01_basic_usage             112L  0C    5m  CC=3      ←0
  │ 04_dsl_usage               111L  0C    7m  CC=1      ←0
  │ 05_dsl_usage               109L  0C    6m  CC=4      ←0
  │ run.sh                     109L  0C    0m  CC=0.0    ←0
  │ merged.yaml                106L  0C    0m  CC=0.0    ←0
  │ demo                       105L  0C    5m  CC=7      ←0
  │ 02_curl_examples.sh        102L  0C    2m  CC=0.0    ←0
  │ merged-strategy.yaml        96L  0C    0m  CC=0.0    ←0
  │ tickets.planfile.yaml       95L  0C    0m  CC=0.0    ←0
  │ run.sh                      92L  0C    1m  CC=0.0    ←0
  │ run.sh                      92L  0C    1m  CC=0.0    ←0
  │ run.sh                      89L  0C    1m  CC=0.0    ←0
  │ planfile.yaml               85L  0C    0m  CC=0.0    ←0
  │ strategy_simple_v2.yaml     80L  0C    0m  CC=0.0    ←0
  │ 01_dsl_usage                75L  0C    0m  CC=0.0    ←0
  │ tickets.planfile.yaml       70L  0C    0m  CC=0.0    ←0
  │ tickets.planfile.yaml       70L  0C    0m  CC=0.0    ←0
  │ validate_with_llx.sh        65L  0C    1m  CC=0.0    ←0
  │ web.json                    62L  0C    0m  CC=0.0    ←0
  │ web-template.json           62L  0C    0m  CC=0.0    ←0
  │ 04_analytics_simple         59L  0C    1m  CC=1      ←0
  │ strategy-export.json        58L  0C    0m  CC=0.0    ←0
  │ test-strategy.json          58L  0C    0m  CC=0.0    ←0
  │ 03_integration_simple       52L  0C    1m  CC=3      ←0
  │ run_all.sh                  49L  0C    1m  CC=0.0    ←0
  │ 01_start_server.sh          47L  0C    0m  CC=0.0    ←0
  │ run_fixed.sh                47L  0C    0m  CC=0.0    ←0
  │ mobile-healthcare.yaml      46L  0C    0m  CC=0.0    ←0
  │ web-ecommerce.yaml          46L  0C    0m  CC=0.0    ←0
  │ ml-finance.yaml             46L  0C    0m  CC=0.0    ←0
  │ security-baseline.yaml      46L  0C    0m  CC=0.0    ←0
  │ jira.planfile.yaml          45L  0C    0m  CC=0.0    ←0
  │ jira.planfile.yaml          43L  0C    0m  CC=0.0    ←0
  │ current.yaml                43L  0C    0m  CC=0.0    ←0
  │ current.yaml                43L  0C    0m  CC=0.0    ←0
  │ test-strategy.yaml          42L  0C    0m  CC=0.0    ←0
  │ web-template.yaml           42L  0C    0m  CC=0.0    ←0
  │ template-mobile-healthcare.yaml    42L  0C    0m  CC=0.0    ←0
  │ template-ml-finance.yaml    42L  0C    0m  CC=0.0    ←0
  │ template-web-ecommerce.yaml    42L  0C    0m  CC=0.0    ←0
  │ gitlab.planfile.yaml        41L  0C    0m  CC=0.0    ←0
  │ run.sh                      40L  0C    0m  CC=0.0    ←0
  │ evolution.toon.yaml         39L  0C    0m  CC=0.0    ←0
  │ run.sh                      38L  0C    0m  CC=0.0    ←0
  │ gitlab.planfile.yaml        38L  0C    0m  CC=0.0    ←0
  │ duplication.toon.yaml       37L  0C    0m  CC=0.0    ←0
  │ github.planfile.yaml        37L  0C    0m  CC=0.0    ←0
  │ github.planfile.yaml        35L  0C    0m  CC=0.0    ←0
  │ run_fixed.sh                35L  0C    0m  CC=0.0    ←0
  │ run.sh                      34L  0C    0m  CC=0.0    ←0
  │ run_all.sh                  30L  0C    0m  CC=0.0    ←0
  │ run.sh                      29L  0C    0m  CC=0.0    ←0
  │ run.sh                      29L  0C    0m  CC=0.0    ←0
  │ run.sh                      29L  0C    0m  CC=0.0    ←0
  │ strategy_free_test.yaml     24L  0C    0m  CC=0.0    ←0
  │ planfile.yaml               18L  0C    0m  CC=0.0    ←0
  │ planfile.yaml               18L  0C    0m  CC=0.0    ←0
  │ run.sh                      17L  0C    0m  CC=0.0    ←0
  │ planfile.yaml               17L  0C    0m  CC=0.0    ←0
  │ ci-workflow.sh              16L  0C    0m  CC=0.0    ←0
  │ analysis.toon.yaml          16L  0C    0m  CC=0.0    ←0
  │ run.sh                      13L  0C    0m  CC=0.0    ←0
  │ run.sh                      13L  0C    0m  CC=0.0    ←0
  │ run.sh                      12L  0C    0m  CC=0.0    ←0
  │ planfile-sync.sh            10L  0C    0m  CC=0.0    ←0
  │ github.state.yaml            7L  0C    0m  CC=0.0    ←0
  │ backlog.yaml                 5L  0C    0m  CC=0.0    ←0
  │ config.yaml                  3L  0C    0m  CC=0.0    ←0
  │ config.yaml                  3L  0C    0m  CC=0.0    ←0
  │ config.yaml                  3L  0C    0m  CC=0.0    ←0
  │ strategy-export-dict.txt     1L  0C    0m  CC=0.0    ←0
  │
  ./                              CC̄=0.8    ←in:0  →out:0
  │ !! goal.yaml                  513L  0C    0m  CC=0.0    ←0
  │ Taskfile.yml               383L  0C    1m  CC=0.0    ←23
  │ pyproject.toml             168L  0C    0m  CC=0.0    ←0
  │ docker-compose.yml         126L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                91L  0C    0m  CC=0.0    ←0
  │ redsl.yaml                  72L  0C    0m  CC=0.0    ←0
  │ test-integrated.yaml        64L  0C    0m  CC=0.0    ←0
  │ project.sh                  48L  0C    0m  CC=0.0    ←0
  │ redsl_refactor_report.toon.yaml    25L  0C    0m  CC=0.0    ←0
  │ redsl_refactor_plan.toon.yaml    22L  0C    0m  CC=0.0    ←0
  │ tree.sh                      1L  0C    0m  CC=0.0    ←0
  │ mcp-server-example           0L  0C    4m  CC=1      ←0
  │ Makefile                     0L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=0.0    ←in:15  →out:0
  │ run_examples.sh            286L  0C   13m  CC=0.0    ←7
  │ docker-entrypoint.sh       174L  0C    5m  CC=0.0    ←0
  │ auto_generate_planfile.sh   124L  0C    0m  CC=0.0    ←0
  │ cleanup_redundant.sh        71L  0C    0m  CC=0.0    ←0
  │ project.sh                  40L  0C    0m  CC=0.0    ←0
  │
  project/                        CC̄=0.0    ←in:0  →out:0
  │ !! calls.yaml                5656L  0C    0m  CC=0.0    ←0
  │ !! map.toon.yaml             1216L  0C  526m  CC=0.0    ←2
  │ !! calls.toon.yaml            547L  0C    0m  CC=0.0    ←0
  │ analysis.toon.yaml         377L  0C    0m  CC=0.0    ←0
  │ analysis.toon.yaml         185L  0C    0m  CC=0.0    ←0
  │ analysis.toon.yaml         185L  0C    0m  CC=0.0    ←0
  │ analysis.toon.yaml         185L  0C    0m  CC=0.0    ←0
  │ duplication.toon.yaml      161L  0C    0m  CC=0.0    ←0
  │ evolution.toon.yaml         65L  0C    0m  CC=0.0    ←0
  │ evolution.toon.yaml         59L  0C    0m  CC=0.0    ←0
  │ project.toon.yaml           53L  0C    0m  CC=0.0    ←0
  │ prompt.txt                  47L  0C    0m  CC=0.0    ←0
  │ validation.toon.yaml        40L  0C    0m  CC=0.0    ←0
  │ validation.toon.yaml         5L  0C    0m  CC=0.0    ←0
  │
  .taskill/                       CC̄=0.0    ←in:0  →out:0
  │ state.json                  13L  0C    0m  CC=0.0    ←0
  │
  web/                            CC̄=0.0    ←in:0  →out:0
  │ web-template.yaml           39L  0C    0m  CC=0.0    ←0
  │
  .planfile/                      CC̄=0.0    ←in:0  →out:0
  │ !! current.yaml              1226L  0C    0m  CC=0.0    ←0
  │ backlog.yaml               202L  0C    0m  CC=0.0    ←0
  │ github.planfile.yaml        19L  0C    0m  CC=0.0    ←0
  │ github.state.yaml           14L  0C    0m  CC=0.0    ←0
  │ config.yaml                  3L  0C    0m  CC=0.0    ←0
  │
  analyses/                       CC̄=0.0    ←in:0  →out:0
  │ !! test-integrated.yaml     289300L  0C    0m  CC=0.0    ←0
  │ !! final-planfile.yaml       1840L  0C    0m  CC=0.0    ←0
  │ !! integrated-planfile.yaml  1668L  0C    0m  CC=0.0    ←0
  │ !! enhanced-analysis.yaml    1311L  0C    0m  CC=0.0    ←0
  │ analysis-generated.yaml    310L  0C    0m  CC=0.0    ←0
  │ sumd.json                  144L  0C    0m  CC=0.0    ←0
  │ refactoring_summary.json    83L  0C    0m  CC=0.0    ←0
  │ llx-driven-strategy.yaml    77L  0C    0m  CC=0.0    ←0
  │ llx-config-for-planfile.yaml    66L  0C    0m  CC=0.0    ←0
  │ SUMR.json                    9L  0C    0m  CC=0.0    ←0
  │
  testql-scenarios/               CC̄=0.0    ←in:0  →out:0
  │ generated-from-pytests.testql.toon.yaml     7L  0C    0m  CC=0.0    ←0
  │ generated-unit-tests.testql.toon.yaml     7L  0C    0m  CC=0.0    ←0
  │
  config/                         CC̄=0.0    ←in:0  →out:0
  │ goal.yaml                  429L  0C    0m  CC=0.0    ←0
  │ pyqual.yaml                190L  0C    0m  CC=0.0    ←0
  │ planfile-auto.yaml         174L  0C    0m  CC=0.0    ←0
  │ mcp-tools.json              87L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                31L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     Dockerfile                                0L
     Makefile                                  0L
     mcp-server-example.py                     0L
     planfile/loaders/__init__.py              0L

COUPLING:
                                  Taskfile  examples.python-api   examples.ecosystem             planfile    examples.rest-api         planfile.cli    planfile.analysis     planfile.loaders              scripts         planfile.api          project.map        planfile.sync   planfile.importers        planfile.core         planfile.llm
             Taskfile                   ──                 ←158                  ←95                  ←27                  ←54                                       ←15                   ←2                                                                                  ←6                                        ←2                   ←1  hub
  examples.python-api                  158                   ──                                        16                                                                                                                                                                                                                                         !! fan-out
   examples.ecosystem                   95                                        ──                                                                                                                                                                                                                                                          ←2  !! fan-out
             planfile                   27                  ←16                                        ──                                       ←20                                         1                                       ←12                    1                                         5                                            hub
    examples.rest-api                   54                                                                                  ──                                                                                                                                                                                                                    !! fan-out
         planfile.cli                                                                                  20                                        ──                                        12                   15                                                              2                                         2                    1  !! fan-out
    planfile.analysis                   15                                                                                                                            ──                                                                                   8                                                                                      !! fan-out
     planfile.loaders                    2                                                             ←1                                       ←12                                        ──                                                                                                                                                     hub
              scripts                                                                                                                           ←15                                                             ──                                                                                                                                hub
         planfile.api                                                                                  12                                                                                                                            ──                                                                                                           !! fan-out
          project.map                                                                                  ←1                                                             ←8                                                                                  ──                                                                                      hub
        planfile.sync                    6                                                                                                       ←2                                                                                                                            ──                                                               
   planfile.importers                                                                                  ←5                                                                                                                                                                                           ──                                            hub
        planfile.core                    2                                                                                                       ←2                                                                                                                                                                      ──                     
         planfile.llm                    1                                         2                                                             ←1                                                                                                                                                                                           ──
  CYCLES: none
  HUB: planfile.importers/ (fan-in=5)
  HUB: planfile/ (fan-in=53)
  HUB: project.map/ (fan-in=9)
  HUB: scripts/ (fan-in=15)
  HUB: planfile.loaders/ (fan-in=13)
  HUB: Taskfile/ (fan-in=361)
  SMELL: examples.python-api/ fan-out=174 → split needed
  SMELL: planfile.api/ fan-out=12 → split needed
  SMELL: examples.ecosystem/ fan-out=95 → split needed
  SMELL: planfile/ fan-out=34 → split needed
  SMELL: planfile.cli/ fan-out=52 → split needed
  SMELL: examples.rest-api/ fan-out=54 → split needed
  SMELL: planfile.analysis/ fan-out=23 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 15 groups | 149f 17240L | 2026-05-03

SUMMARY:
  files_scanned: 149
  total_lines:   17240
  dup_groups:    15
  dup_fragments: 40
  saved_lines:   172
  scan_ms:       6825

HOTSPOTS[7] (files with most duplication):
  examples/rest-api/04_dsl_usage.py  dup=63L  groups=2  frags=5  (0.4%)
  planfile/cli/project_detector/gates.py  dup=32L  groups=2  frags=4  (0.2%)
  planfile/cli/groups/sync/commands.py  dup=28L  groups=1  frags=4  (0.2%)
  planfile/cli/groups/sync/core.py  dup=24L  groups=1  frags=2  (0.1%)
  planfile/cli/groups/ticket/commands.py  dup=18L  groups=1  frags=2  (0.1%)
  planfile/cli/core/console.py  dup=15L  groups=1  frags=5  (0.1%)
  planfile/sync/base.py  dup=14L  groups=1  frags=1  (0.1%)

DUPLICATES[15] (ranked by impact):
  [bef34080d3b159fe]   STRU  example_dsl_command  L=11 N=3 saved=22 sim=1.00
      examples/rest-api/04_dsl_usage.py:6-16  (example_dsl_command)
      examples/rest-api/04_dsl_usage.py:19-29  (example_dsl_create_ticket)
      examples/rest-api/04_dsl_usage.py:32-42  (example_dsl_update_ticket)
  [73f23dc09aac9b7a]   STRU  github_cmd  L=7 N=4 saved=21 sim=1.00
      planfile/cli/groups/sync/commands.py:15-21  (github_cmd)
      planfile/cli/groups/sync/commands.py:24-30  (gitlab_cmd)
      planfile/cli/groups/sync/commands.py:33-39  (jira_cmd)
      planfile/cli/groups/sync/commands.py:42-48  (markdown_cmd)
  [647474f57d8a2dab]   STRU  register_auto_commands  L=8 N=3 saved=16 sim=1.00
      planfile/cli/groups/auto/__init__.py:11-18  (register_auto_commands)
      planfile/cli/groups/backlog/__init__.py:11-18  (register_backlog_commands)
      planfile/cli/groups/generate/__init__.py:11-18  (register_generate_commands)
  [d2c29bc2b85437aa]   STRU  example_dsl_sprint  L=15 N=2 saved=15 sim=1.00
      examples/rest-api/04_dsl_usage.py:45-59  (example_dsl_sprint)
      examples/rest-api/04_dsl_usage.py:62-76  (example_dsl_validate_sync)
  [f071e098e43958d3]   STRU  map_priority  L=14 N=2 saved=14 sim=1.00
      planfile/sync/base.py:66-79  (map_priority)
      planfile/sync/jira.py:65-78  (map_priority)
  [21eb3398cdd6a2b6]   STRU  print_success  L=3 N=5 saved=12 sim=1.00
      planfile/cli/core/console.py:9-11  (print_success)
      planfile/cli/core/console.py:14-16  (print_error)
      planfile/cli/core/console.py:19-21  (print_warning)
      planfile/cli/core/console.py:24-26  (print_info)
      planfile/cli/core/console.py:29-31  (print_dim)
  [84118158d8b5d9f1]   STRU  register_apply_commands  L=3 N=5 saved=12 sim=1.00
      planfile/cli/groups/apply/__init__.py:9-11  (register_apply_commands)
      planfile/cli/groups/examples/__init__.py:9-11  (register_examples_commands)
      planfile/cli/groups/health/__init__.py:9-11  (register_health_commands)
      planfile/cli/groups/init/__init__.py:9-11  (register_init_commands)
      planfile/cli/groups/review/__init__.py:9-11  (register_review_commands)
  [6a6c4ffd98c596b0]   STRU  _collect_tickets_from_sprint  L=12 N=2 saved=12 sim=1.00
      planfile/cli/groups/sync/core.py:58-69  (_collect_tickets_from_sprint)
      planfile/cli/groups/sync/core.py:72-83  (_collect_tickets_from_backlog)
  [743611597bf1e270]   STRU  ticket_done  L=9 N=2 saved=9 sim=1.00
      planfile/cli/groups/ticket/commands.py:280-288  (ticket_done)
      planfile/cli/groups/ticket/commands.py:290-298  (ticket_start)
  [1d3d96e641f80678]   STRU  _detect_docker_gates  L=9 N=2 saved=9 sim=1.00
      planfile/cli/project_detector/gates.py:40-48  (_detect_docker_gates)
      planfile/cli/project_detector/gates.py:145-153  (_detect_doc_gates)
  [9c4f9ae7fbca56f4]   STRU  _has_mypy_config  L=7 N=2 saved=7 sim=1.00
      planfile/cli/project_detector/gates.py:103-109  (_has_mypy_config)
      planfile/cli/project_detector/gates.py:136-142  (_has_bandit_config)
  [ea2851389f454151]   STRU  import_json  L=7 N=2 saved=7 sim=1.00
      planfile/importers/json_importer.py:8-14  (import_json)
      planfile/importers/yaml_importer.py:8-14  (import_yaml)
  [a9991ab6527fc886]   EXAC  _load_strategy  L=6 N=2 saved=6 sim=1.00
      planfile/ticket_validation.py:16-21  (_load_strategy)
      planfile/todo_sync.py:15-20  (_load_strategy)
  [41220f657f2d6a8d]   STRU  done_ticket  L=6 N=2 saved=6 sim=1.00
      planfile/api/server.py:149-154  (done_ticket)
      planfile/api/server.py:158-163  (start_ticket)
  [3252487e1015a40a]   STRU  _find_readme_description  L=4 N=2 saved=4 sim=1.00
      planfile/cli/project_detector/readme.py:57-60  (_find_readme_description)
      planfile/cli/project_detector/readme.py:63-66  (_find_readme_goal)

REFACTOR[15] (ranked by priority):
  [1] ○ extract_function   → examples/rest-api/utils/example_dsl_command.py
      WHY: 3 occurrences of 11-line block across 1 files — saves 22 lines
      FILES: examples/rest-api/04_dsl_usage.py
  [2] ○ extract_function   → planfile/cli/groups/sync/utils/github_cmd.py
      WHY: 4 occurrences of 7-line block across 1 files — saves 21 lines
      FILES: planfile/cli/groups/sync/commands.py
  [3] ○ extract_function   → planfile/cli/groups/utils/register_auto_commands.py
      WHY: 3 occurrences of 8-line block across 3 files — saves 16 lines
      FILES: planfile/cli/groups/auto/__init__.py, planfile/cli/groups/backlog/__init__.py, planfile/cli/groups/generate/__init__.py
  [4] ○ extract_function   → examples/rest-api/utils/example_dsl_sprint.py
      WHY: 2 occurrences of 15-line block across 1 files — saves 15 lines
      FILES: examples/rest-api/04_dsl_usage.py
  [5] ○ extract_function   → planfile/sync/utils/map_priority.py
      WHY: 2 occurrences of 14-line block across 2 files — saves 14 lines
      FILES: planfile/sync/base.py, planfile/sync/jira.py
  [6] ○ extract_function   → planfile/cli/core/utils/print_success.py
      WHY: 5 occurrences of 3-line block across 1 files — saves 12 lines
      FILES: planfile/cli/core/console.py
  [7] ○ extract_function   → planfile/cli/groups/utils/register_apply_commands.py
      WHY: 5 occurrences of 3-line block across 5 files — saves 12 lines
      FILES: planfile/cli/groups/apply/__init__.py, planfile/cli/groups/examples/__init__.py, planfile/cli/groups/health/__init__.py, planfile/cli/groups/init/__init__.py, planfile/cli/groups/review/__init__.py
  [8] ○ extract_function   → planfile/cli/groups/sync/utils/_collect_tickets_from_sprint.py
      WHY: 2 occurrences of 12-line block across 1 files — saves 12 lines
      FILES: planfile/cli/groups/sync/core.py
  [9] ○ extract_function   → planfile/cli/groups/ticket/utils/ticket_done.py
      WHY: 2 occurrences of 9-line block across 1 files — saves 9 lines
      FILES: planfile/cli/groups/ticket/commands.py
  [10] ○ extract_function   → planfile/cli/project_detector/utils/_detect_docker_gates.py
      WHY: 2 occurrences of 9-line block across 1 files — saves 9 lines
      FILES: planfile/cli/project_detector/gates.py
  [11] ○ extract_function   → planfile/cli/project_detector/utils/_has_mypy_config.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: planfile/cli/project_detector/gates.py
  [12] ○ extract_function   → planfile/importers/utils/import_json.py
      WHY: 2 occurrences of 7-line block across 2 files — saves 7 lines
      FILES: planfile/importers/json_importer.py, planfile/importers/yaml_importer.py
  [13] ○ extract_function   → planfile/utils/_load_strategy.py
      WHY: 2 occurrences of 6-line block across 2 files — saves 6 lines
      FILES: planfile/ticket_validation.py, planfile/todo_sync.py
  [14] ○ extract_function   → planfile/api/utils/done_ticket.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: planfile/api/server.py
  [15] ○ extract_function   → planfile/cli/project_detector/utils/_find_readme_description.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: planfile/cli/project_detector/readme.py

QUICK_WINS[14] (low risk, high savings — do first):
  [1] extract_function   saved=22L  → examples/rest-api/utils/example_dsl_command.py
      FILES: 04_dsl_usage.py
  [2] extract_function   saved=21L  → planfile/cli/groups/sync/utils/github_cmd.py
      FILES: commands.py
  [3] extract_function   saved=16L  → planfile/cli/groups/utils/register_auto_commands.py
      FILES: __init__.py, __init__.py, __init__.py
  [4] extract_function   saved=15L  → examples/rest-api/utils/example_dsl_sprint.py
      FILES: 04_dsl_usage.py
  [5] extract_function   saved=14L  → planfile/sync/utils/map_priority.py
      FILES: base.py, jira.py
  [6] extract_function   saved=12L  → planfile/cli/core/utils/print_success.py
      FILES: console.py
  [7] extract_function   saved=12L  → planfile/cli/groups/utils/register_apply_commands.py
      FILES: __init__.py, __init__.py, __init__.py +2
  [8] extract_function   saved=12L  → planfile/cli/groups/sync/utils/_collect_tickets_from_sprint.py
      FILES: core.py
  [9] extract_function   saved=9L  → planfile/cli/groups/ticket/utils/ticket_done.py
      FILES: commands.py
  [10] extract_function   saved=9L  → planfile/cli/project_detector/utils/_detect_docker_gates.py
      FILES: gates.py

EFFORT_ESTIMATE (total ≈ 5.7h):
  medium example_dsl_command                 saved=22L  ~44min
  medium github_cmd                          saved=21L  ~42min
  medium register_auto_commands              saved=16L  ~32min
  medium example_dsl_sprint                  saved=15L  ~30min
  easy   map_priority                        saved=14L  ~28min
  easy   print_success                       saved=12L  ~24min
  easy   register_apply_commands             saved=12L  ~24min
  easy   _collect_tickets_from_sprint        saved=12L  ~24min
  easy   ticket_done                         saved=9L  ~18min
  easy   _detect_docker_gates                saved=9L  ~18min
  ... +5 more (~60min)

METRICS-TARGET:
  dup_groups:  15 → 0
  saved_lines: 172 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 1207 func | 103f | 2026-05-03

NEXT[6] (ranked by impact):
  [1] !! SPLIT           planfile/cli/groups/ticket/commands.py
      WHY: 519L, 0 classes, max CC=21
      EFFORT: ~4h  IMPACT: 10899

  [2] !! SPLIT           planfile/testql_integration.py
      WHY: 711L, 0 classes, max CC=15
      EFFORT: ~4h  IMPACT: 10665

  [3] !! SPLIT-FUNC      handle_tool_call  CC=27  fan=22
      WHY: CC=27 exceeds 15
      EFFORT: ~1h  IMPACT: 594

  [4] !  SPLIT-FUNC      upsert_testql_tickets  CC=15  fan=20
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 300

  [5] !  SPLIT-FUNC      ticket_bulk_update  CC=21  fan=13
      WHY: CC=21 exceeds 15
      EFFORT: ~1h  IMPACT: 273

  [6] !  SPLIT-FUNC      DSLParser._extract_modifiers  CC=15  fan=10
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 150


RISKS[2]:
  ⚠ Splitting planfile/testql_integration.py may break 35 import paths
  ⚠ Splitting planfile/cli/groups/ticket/commands.py may break 23 import paths

METRICS-TARGET:
  CC̄:          2.3 → ≤1.6
  max-CC:      27 → ≤13
  god-modules: 2 → 0
  high-CC(≥15): 4 → ≤2
  hub-types:   0 → ≤0

PATTERNS (language parser shared logic):
  _extract_declarations() in base.py — unified extraction for:
    - TypeScript: interfaces, types, classes, functions, arrow funcs
    - PHP: namespaces, traits, classes, functions, includes
    - Ruby: modules, classes, methods, requires
    - C++: classes, structs, functions, #includes
    - C#: classes, interfaces, methods, usings
    - Java: classes, interfaces, methods, imports
    - Go: packages, functions, structs
    - Rust: modules, functions, traits, use statements

  Shared regex patterns per language:
    - import: language-specific import/require/using patterns
    - class: class/struct/trait declarations with inheritance
    - function: function/method signatures with visibility
    - brace_tracking: for C-family languages ({ })
    - end_keyword_tracking: for Ruby (module/class/def...end)

  Benefits:
    - Consistent extraction logic across all languages
    - Reduced code duplication (~70% reduction in parser LOC)
    - Easier maintenance: fix once, apply everywhere
    - Standardized FunctionInfo/ClassInfo models

HISTORY:
  prev CC̄=2.4 → now CC̄=2.3
```

### Validation (`project/validation.toon.yaml`)

```toon markpact:analysis path=project/validation.toon.yaml
# vallm batch | 213f | 155✓ 5⚠ 1✗ | 2026-04-19

SUMMARY:
  scanned: 213  passed: 155 (72.8%)  warnings: 5  errors: 1  unsupported: 57

WARNINGS[5]{path,score}:
  planfile/builder.py,0.97
    issues[1]{rule,severity,message,line}:
      complexity.lizard_length,warning,ask_llm_questions: 119 lines exceeds limit 100,77
  planfile/cli/project_detector/inference.py,0.97
    issues[2]{rule,severity,message,line}:
      complexity.cyclomatic,warning,_infer_python_project_type has cyclomatic complexity 17 (max: 15),8
      complexity.lizard_cc,warning,_infer_python_project_type: CC=17 exceeds limit 15,8
  planfile/cli/project_detector/readme.py,0.97
    issues[2]{rule,severity,message,line}:
      complexity.cyclomatic,warning,_find_readme_content has cyclomatic complexity 16 (max: 15),9
      complexity.lizard_cc,warning,_find_readme_content: CC=16 exceeds limit 15,9
  planfile/cli/project_detector/structure.py,0.97
    issues[2]{rule,severity,message,line}:
      complexity.cyclomatic,warning,_analyze_directory_structure has cyclomatic complexity 20 (max: 15),8
      complexity.lizard_cc,warning,_analyze_directory_structure: CC=20 exceeds limit 15,8
  planfile/core/models/strategy.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.maintainability,warning,Low maintainability index: 16.2 (threshold: 20),

ERRORS[1]{path,score}:
  planfile/examples.py,0.64
    issues[5]{rule,severity,message,line}:
      python.import.resolvable,error,Module 'llx.planfile' not found,10
      python.import.resolvable,error,Module 'llx.planfile' not found,23
      python.import.resolvable,error,Module 'llx.planfile' not found,36
      python.import.resolvable,error,Module 'llx.planfile' not found,49
      python.import.resolvable,error,Module 'llx.planfile.models' not found,67

UNSUPPORTED[5]{bucket,count}:
  *.md,35
  Dockerfile*,1
  *.txt,1
  *.yml,3
  other,17
```

## Intent

SDLC automation platform - strategic project management with CI/CD integration and automated bug-fix loops
