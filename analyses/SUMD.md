# Planfile

SDLC automation platform - strategic project management with CI/CD integration and automated bug-fix loops

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Workflows](#workflows)
- [Quality Pipeline (`pyqual.yaml`)](#quality-pipeline-pyqualyaml)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [Release Management (`goal.yaml`)](#release-management-goalyaml)
- [Makefile Targets](#makefile-targets)
- [Code Analysis](#code-analysis)
- [Source Map](#source-map)
- [Intent](#intent)

## Metadata

- **name**: `planfile`
- **version**: `0.1.59`
- **python_requires**: `>=3.10`
- **license**: Apache-2.0
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, app.doql.css, pyqual.yaml, goal.yaml, Dockerfile, docker-compose.yml, src(8 mod), project/(1 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.css`)

```css markpact:doql path=app.doql.css
app {
  name: "planfile";
  version: "0.1.58";
}

entity[name="TicketSource"] {

}

entity[name="Ticket"] {

}

entity[name="ModelHints"] {

}

entity[name="Task"] {

}

entity[name="Sprint"] {

}

entity[name="QualityGate"] {

}

entity[name="Goal"] {

}

entity[name="Strategy"] {

}

database[name="postgres"] {
  type: "postgresql";
  url: env.DATABASE_URL;
}

database[name="redis"] {
  type: "redis";
  url: env.REDIS_URL;
}

interface[type="cli"] {
  framework: argparse;
}
interface[type="cli"] page[name="planfile"] {

}

integration[name="email"] {
  type: "smtp";
}

integration[name="github"] {
  type: "scm";
}

workflow[name="install"] {
  trigger: "manual";
  step-1: run cmd=pip install -e ".[all]";
  step-2: run cmd=pip install llx;
}

workflow[name="test"] {
  trigger: "manual";
  step-1: run cmd=pytest --cov=src --cov-report=html --cov-report=term;
}

workflow[name="docker-build"] {
  trigger: "manual";
  step-1: run cmd=docker build -t planfile/runner:latest .;
}

workflow[name="docker-run"] {
  trigger: "manual";
  step-1: run cmd=docker-compose up -d planfile-runner;
  step-2: run cmd=docker-compose logs -f planfile-runner;
}

workflow[name="docker-stop"] {
  trigger: "manual";
  step-1: run cmd=docker-compose down;
}

workflow[name="docker-clean"] {
  trigger: "manual";
  step-1: run cmd=docker-compose down -v;
  step-2: run cmd=docker system prune -f;
}

workflow[name="ci-loop"] {
  trigger: "manual";
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
  trigger: "manual";
  step-1: run cmd=python -m venv .venv;
  step-2: run cmd=source .venv/bin/activate && pip install -e ".[dev]";
  step-3: run cmd=pre-commit install;
}

workflow[name="lint"] {
  trigger: "manual";
  step-1: run cmd=ruff check src/ tests/;
  step-2: run cmd=ruff format --check src/ tests/;
}

workflow[name="format"] {
  trigger: "manual";
  step-1: run cmd=ruff check --fix src/ tests/;
  step-2: run cmd=ruff format src/ tests/;
}

workflow[name="example-github"] {
  trigger: "manual";
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
  trigger: "manual";
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
  trigger: "manual";
  step-1: run cmd=planfile auto ci-status;
}

workflow[name="logs"] {
  trigger: "manual";
  step-1: run cmd=docker-compose logs -f planfile-runner;
}

workflow[name="clean"] {
  trigger: "manual";
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
  trigger: "manual";
  step-1: run cmd=python -c "import planfile; print(planfile.__version__)";
}

workflow[name="bump-patch"] {
  trigger: "manual";
  step-1: run cmd=bump2version patch;
}

workflow[name="bump-minor"] {
  trigger: "manual";
  step-1: run cmd=bump2version minor;
}

workflow[name="bump-major"] {
  trigger: "manual";
  step-1: run cmd=bump2version major;
}

workflow[name="publish"] {
  trigger: "manual";
  step-1: run cmd=python3 -m build;
  step-2: run cmd=twine upload dist/*;
}

workflow[name="pipeline-test"] {
  trigger: "manual";
  step-1: run cmd=echo "Running full CI/CD pipeline locally...";
  step-2: run cmd=echo "Step 1: Install dependencies";
  step-3: run cmd=make install;
  step-4: run cmd=echo "Step 2: Run tests";
  step-5: run cmd=make test;
  step-6: run cmd=echo "Step 3: Run CI loop";
  step-7: run cmd=make ci-loop STRATEGY=examples/strategies/onboarding.yaml BACKENDS=github MAX_ITERATIONS=1;
}

workflow[name="pipeline-docker"] {
  trigger: "manual";
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
  trigger: "manual";
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
  trigger: "manual";
  step-1: run cmd=planfile strategy review \;
  step-2: run cmd=--strategy examples/strategies/onboarding.yaml \;
  step-3: run cmd=--project . \;
  step-4: run cmd=--backend github;
}

workflow[name="test-github"] {
  trigger: "manual";
  step-1: run cmd=echo "Testing GitHub integration...";
  step-2: run cmd=if [ -z "$(GITHUB_TOKEN)" ] || [ -z "$(GITHUB_REPO)" ]; then \;
  step-3: run cmd=echo "Set GITHUB_TOKEN and GITHUB_REPO"; \;
  step-4: run cmd=exit 1; \;
  step-5: run cmd=fi;
  step-6: run cmd=python3 -m tests.integration.test_github;
}

workflow[name="test-jira"] {
  trigger: "manual";
  step-1: run cmd=echo "Testing Jira integration...";
  step-2: run cmd=if [ -z "$(JIRA_TOKEN)" ] || [ -z "$(JIRA_URL)" ]; then \;
  step-3: run cmd=echo "Set JIRA_TOKEN and JIRA_URL"; \;
  step-4: run cmd=exit 1; \;
  step-5: run cmd=fi;
  step-6: run cmd=python -m tests.integration.test_jira;
}

workflow[name="docs"] {
  trigger: "manual";
  step-1: run cmd=echo "Generating documentation...";
  step-2: run cmd=cd docs && make html;
}

workflow[name="serve-docs"] {
  trigger: "manual";
  step-1: run cmd=echo "Serving documentation...";
  step-2: run cmd=cd docs/_build/html && python3 -m http.server 8080;
}

workflow[name="quick-start"] {
  trigger: "manual";
  step-1: run cmd=echo "Quick start with Planfile";
  step-2: run cmd=echo "==========================";
  step-3: run cmd=echo "1. Install: make install";
  step-4: run cmd=echo "2. Configure: export GITHUB_TOKEN=your_token";
  step-5: run cmd=echo "3. Run: make ci-loop STRATEGY=examples/strategies/onboarding.yaml";
  step-6: run cmd=echo "";
  step-7: run cmd=echo "For Docker: make docker-build && make docker-run";
}

workflow[name="fmt"] {
  trigger: "manual";
  step-1: run cmd=ruff format .;
}

workflow[name="build"] {
  trigger: "manual";
  step-1: run cmd=python -m build;
}

workflow[name="health"] {
  trigger: "manual";
  step-1: run cmd=docker compose ps;
  step-2: run cmd=docker compose exec app echo "Health check passed";
}

workflow[name="up"] {
  trigger: "manual";
  step-1: run cmd=docker compose up -d;
}

workflow[name="down"] {
  trigger: "manual";
  step-1: run cmd=docker compose down;
}

workflow[name="ps"] {
  trigger: "manual";
  step-1: run cmd=docker compose ps;
}

workflow[name="import-makefile-hint"] {
  trigger: "manual";
  step-1: run cmd=echo 'Run: taskfile import Makefile to import existing targets.';
}

workflow[name="help"] {
  trigger: "manual";
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
  step-13: run cmd=echo "  make install                    # Install with all backends; 
  step-14: run cmd=echo "  make ci-loop BACKENDS=github    # Run with GitHub only; 
  step-15: run cmd=echo "  make docker-run AUTO_FIX=true   # Run with auto-fix enabled; 
}

deploy {
  target: docker-compose;
  compose_file: docker-compose.yml;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: ".env";
}

workflow[name="all"] {
  trigger: "manual";
  step-1: run cmd=taskfile run install;
  step-2: run cmd=taskfile run lint;
  step-3: run cmd=taskfile run test;
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

## Interfaces

### CLI Entry Points

- `planfile`

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

## Quality Pipeline (`pyqual.yaml`)

```yaml markpact:pyqual path=pyqual.yaml
pipeline:
  name: quality-loop-with-llx

  # Quality gates — pipeline iterates until ALL pass
  # ONLY metrics with actual data (null values removed)
  metrics:
    # Code complexity & quality (active)
    cc_max: 10                    # cyclomatic complexity (current: 4.1)
    critical_max: 20              # critical issues (current: 17)
    
    # Test & validation (active)
    vallm_pass_min: 75            # vallm pass rate % (current: 76.1)
    coverage_min: 4               # test coverage % (current: 4.6)
    
    # Lint & style (active)
    ruff_fatal_max: 15            # fatal lint errors (current: 13)
    ruff_errors_max: 600          # total errors (current: 523)
    
    # NOTE: Disabled gates (no data from collectors):
    # documentation_score_min, readme_completeness_min
    # secrets_found_max, security_vuln_critical_max, security_vuln_high_max
    # license_exists_min, pyproject_completeness_min

  # Custom tool definitions
  custom_tools:
    - name: code2llm_vallm
      binary: .venv/bin/code2llm
      command: >-
        .venv/bin/code2llm {workdir} -f toon -o ./project --no-chunk
        --exclude .git venv dist __pycache__ .pytest_cache .mypy_cache .ruff_cache
        .code2llm_cache build *.egg-info
      output: ""
      allow_failure: false

    - name: vallm_src
      binary: venv/bin/vallm
      command: >-
        venv/bin/vallm batch {workdir}/src --recursive --format toon --output ./project
        --exclude ".git" --exclude "venv" --exclude "dist" --exclude "__pycache__"
        --exclude ".pytest_cache" --exclude ".mypy_cache" --exclude ".ruff_cache"
        --exclude ".code2llm_cache" --exclude "build" --exclude "*.egg-info"
        --exclude "test-integrated.yaml" --exclude "examples/llm-integration/llm-config.yaml"
        --exclude "mcp-server-example.py" --exclude "examples/*" --exclude "test_*.py"
        --exclude "test*.py" --exclude "test*.yaml" --exclude "test*.sh"
        --exclude "run_examples.sh" --exclude "test_checkbox_tickets.py"
        --exclude "test_mixed_format.py" --exclude "test_chars.py"
        --exclude "test_regex.py" --exclude "test_regex2.py" --exclude "test_strategy.py"
        --exclude "test_improvements.py" --exclude "test_integration.py"
        --exclude "test_markdown_integration.py" --exclude "test_planfile_final.py"
      output: ""
      allow_failure: false

    - name: vallm_verify
      binary: venv/bin/vallm
      command: >-
        venv/bin/vallm batch {workdir}/src --recursive --no-complexity --format toon --output ./project/verify
        --exclude ".git" --exclude "venv" --exclude "dist" --exclude "__pycache__"
        --exclude ".pytest_cache" --exclude ".mypy_cache" --exclude ".ruff_cache"
        --exclude ".code2llm_cache" --exclude "build" --exclude "*.egg-info"
        --exclude "test-integrated.yaml" --exclude "examples/llm-integration/llm-config.yaml"
        --exclude "mcp-server-example.py" --exclude "examples/*" --exclude "test_*.py"
        --exclude "test*.py" --exclude "test*.yaml" --exclude "test*.sh"
        --exclude "run_examples.sh" --exclude "test_checkbox_tickets.py"
        --exclude "test_mixed_format.py" --exclude "test_chars.py"
        --exclude "test_regex.py" --exclude "test_regex2.py" --exclude "test_strategy.py"
        --exclude "test_improvements.py" --exclude "test_integration.py"
        --exclude "test_markdown_integration.py" --exclude "test_planfile_final.py"
      output: ""
      allow_failure: false

  # Pipeline stages
  stages:
    - name: setup
      run: |
        set -e
        echo "=== pyqual dependency check ==="
        for pkg in code2llm vallm prefact llx pytest-cov goal; do
          if python -m pip show "$pkg" >/dev/null 2>&1; then
            echo "  ✓ $pkg"
          else
            echo "  ✗ $pkg — installing…"
            pip install -q "$pkg" || echo "  ⚠ $pkg install failed (optional)"
          fi
        done
        if command -v claude >/dev/null 2>&1; then
          echo "  ✓ claude $(claude --version 2>/dev/null)"
        else
          echo "  ✗ claude — not installed"
        fi
        echo "=== setup done ==="
      when: first_iteration
      timeout: 300

    - name: lint
      tool: ruff
      optional: true

    - name: test
      run: .venv/bin/python -m pytest -q --tb=short --cov=src/vallm --cov-report=term-missing --cov-report=json:.pyqual/coverage.json
      when: always

    - name: prefact
      tool: prefact
      optional: true
      when: metrics_fail
      timeout: 900

    - name: fix
      tool: llx-fix
      optional: true
      when: metrics_fail
      timeout: 1800

    - name: verify
      tool: vallm_verify
      optional: true
      when: after_fix
      timeout: 300

    - name: push
      run: |
        if [ -n "$(git status --porcelain)" ]; then
          git add -A
          git commit -m "chore: pyqual auto-commit [skip ci]" 2>/dev/null || true
          git push origin HEAD
        else
          echo "No changes to push"
        fi
      when: metrics_pass
      optional: true
      timeout: 120

    - name: publish
      run: make publish
      when: metrics_pass
      optional: true
      timeout: 300

    - name: validate_deploy
      run: |
        echo "=== Validating deploy ==="
        errors=0
        
        # Check push - verify recent pyqual commit
        last_commit=$(git log -1 --pretty=%B 2>/dev/null)
        if echo "$last_commit" | grep -q "pyqual auto-commit"; then
          echo "✓ Push validated: recent commit found"
        else
          echo "✗ Push failed: no pyqual auto-commit found"
          errors=$((errors + 1))
        fi
        
        # Check publish - verify wheel was built successfully
        # Get wheel from today
        today_wheel=$(find dist -name "*.whl" -newer .pyqual/pipeline.db 2>/dev/null | head -1)
        if [ -n "$today_wheel" ]; then
          echo "✓ Publish validated: fresh wheel found: $(basename $today_wheel)"
        else
          echo "✗ Publish failed: no fresh wheel found (checked dist/*.whl)"
          errors=$((errors + 1))
        fi
        
        # Summary
        if [ $errors -eq 0 ]; then
          echo "=== Deploy validation PASSED ==="
          exit 0
        else
          echo "=== Deploy validation FAILED ($errors errors) ==="
          exit 1
        fi
      when: metrics_pass
      optional: true
      timeout: 30

    - name: markdown_report
      run: python3 -m pyqual.report_generator
      when: always
      optional: true
      timeout: 30

  # Loop behavior
  loop:
    max_iterations: 5
    on_fail: report

  # Environment
  env:
    LLM_MODEL: openrouter/x-ai/grok-code-fast-1
    LLX_DEFAULT_TIER: balanced
    LLX_VERBOSE: true
```

## Configuration

```yaml
project:
  name: planfile
  version: 0.1.59
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
- **commits**: `conventional` scope=`strategy`
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
# planfile | 207f 27239L | python:158,shell:37,css:6,javascript:6 | 2026-04-19
# stats: 356 func | 73 cls | 207 mod | CC̄=4.3 | critical:30 | cycles:0
# alerts[5]: CC _analyze_directory_structure=20; CC _infer_python_project_type=17; CC _find_readme_content=16; CC test_checkbox_ticket_parsing=16; CC demo_checkbox_tickets=15
# hotspots[5]: create_examples_app fan=23; review_strategy_cli fan=21; auto_loop_cmd fan=20; example_metric_driven_planning fan=18; analyze_text fan=17
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[207]:
  app.doql.css,361
  auto_generate_planfile.sh,125
  cleanup_redundant.sh,72
  docker-entrypoint.sh,175
  examples/PROPOSED_API_IMPROVEMENTS.py,218
  examples/advanced-usage/ci-workflow.sh,17
  examples/advanced-usage/run.sh,30
  examples/bash-generation/test_planfile_generation.sh,278
  examples/bash-generation/verify_planfile.sh,246
  examples/checkbox-tickets/demo.py,110
  examples/checkbox-tickets/run.sh,35
  examples/cli-commands/run.sh,30
  examples/cli-commands/run_fixed.sh,36
  examples/code2llm/run.sh,110
  examples/comprehensive-example/run.sh,30
  examples/demo-without-keys/run.sh,18
  examples/ecosystem/01_full_workflow.sh,353
  examples/ecosystem/02_mcp_integration.py,382
  examples/ecosystem/03_proxy_routing.py,369
  examples/ecosystem/04_llx_integration.py,504
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
  examples/multi-ticket/run.sh,167
  examples/python-api/01_basic_usage.py,113
  examples/python-api/02_ticket_management.py,173
  examples/python-api/03_integration.py,219
  examples/python-api/03_integration_simple.py,53
  examples/python-api/04_advanced_filtering.py,162
  examples/python-api/04_analytics_simple.py,60
  examples/python-api/run_all.sh,31
  examples/quick-start/run.sh,41
  examples/quick-start/run_fixed.sh,48
  examples/readme-tests/test_readme_examples.sh,159
  examples/redup/run.sh,129
  examples/rest-api/01_start_server.sh,48
  examples/rest-api/02_curl_examples.sh,103
  examples/rest-api/03_python_client.py,251
  examples/rest-api/04_javascript_client.js,153
  examples/rest-api/05_integration_test.py,185
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
  mcp-server-example.py,29
  planfile/__init__.py,168
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
  planfile/api/server.py,98
  planfile/builder.py,386
  planfile/ci.py,316
  planfile/cli/__init__.py,1
  planfile/cli/__main__.py,5
  planfile/cli/auto_loop.py,27
  planfile/cli/commands.py,60
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
  planfile/cli/groups/sync/__init__.py,19
  planfile/cli/groups/sync/commands.py,74
  planfile/cli/groups/sync/core.py,257
  planfile/cli/groups/ticket/__init__.py,39
  planfile/cli/groups/ticket/commands.py,293
  planfile/cli/groups/validate/__init__.py,12
  planfile/cli/groups/validate/commands.py,43
  planfile/cli/project_detector/__init__.py,24
  planfile/cli/project_detector/base.py,35
  planfile/cli/project_detector/fallback.py,67
  planfile/cli/project_detector/gates.py,171
  planfile/cli/project_detector/git.py,37
  planfile/cli/project_detector/inference.py,88
  planfile/cli/project_detector/license.py,31
  planfile/cli/project_detector/main.py,89
  planfile/cli/project_detector/model_tier.py,61
  planfile/cli/project_detector/package.py,74
  planfile/cli/project_detector/pyproject.py,118
  planfile/cli/project_detector/readme.py,72
  planfile/cli/project_detector/structure.py,61
  planfile/cli/project_detector.py,20
  planfile/core/__init__.py,6
  planfile/core/models/__init__.py,64
  planfile/core/models/base.py,47
  planfile/core/models/strategy.py,260
  planfile/core/models/ticket.py,52
  planfile/core/models.py,8
  planfile/core/store.py,12
  planfile/core/store_files.py,32
  planfile/core/store_tickets.py,55
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
  planfile/mcp/server.py,210
  planfile/models.py,22
  planfile/runner.py,419
  planfile/server_common.py,15
  planfile/sync/__init__.py,26
  planfile/sync/base.py,237
  planfile/sync/generic.py,217
  planfile/sync/github.py,241
  planfile/sync/gitlab.py,234
  planfile/sync/jira.py,281
  planfile/sync/markdown_backend/__init__.py,5
  planfile/sync/markdown_backend/backend.py,51
  planfile/sync/markdown_backend/constants.py,6
  planfile/sync/markdown_backend/files.py,25
  planfile/sync/markdown_backend/tickets.py,111
  planfile/sync/markdown_backend.py,5
  planfile/sync/mock.py,161
  planfile/sync/operations.py,260
  planfile/sync/state.py,47
  planfile/sync/utils.py,12
  planfile/utils/__init__.py,1
  planfile/utils/metrics.py,228
  planfile/utils/priorities.py,112
  project.sh,40
  run_examples.sh,287
  test_chars.py,10
  test_checkbox_tickets.py,113
  test_improvements.py,175
  test_integration.py,121
  test_markdown_integration.py,78
  test_mixed_format.py,50
  test_planfile_final.py,156
  test_regex.py,32
  test_regex2.py,21
  test_strategy.py,62
  tests/htmlcov/coverage_html_cb_dd2e7eb5.js,736
  tests/htmlcov/style_cb_9ff733b0.css,390
  tests/llm_adapters.py,488
  tests/test_strategy.py,73
D:
  examples/PROPOSED_API_IMPROVEMENTS.py:
    e: TicketLogger,PlanfileStoreExtended
    TicketLogger: __init__(2),error(3),metric_alert(3),catch_errors(1)  # Native ticket logging - replaces 80-line example.
    PlanfileStoreExtended: stats(0),export(2),search(2)  # Extended store with analytics and export.
  examples/checkbox-tickets/demo.py:
    e: demo_checkbox_tickets
    demo_checkbox_tickets()
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
    e: example_cli_tool_integration,example_monitoring_integration,example_ci_pipeline_integration,example_custom_decorator,main,TicketLogger
    TicketLogger: __init__(1),error(3),warning(2),metric_alert(3)  # Logger that creates tickets for errors and warnings.
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
  examples/rest-api/03_python_client.py:
    e: example_basic_operations,example_bulk_operations,example_workflow,example_error_handling,main,PlanfileClient
    PlanfileClient: __init__(1),_request(2),health(0),list_tickets(3),create_ticket(5),get_ticket(1),update_ticket(1),move_ticket(2),delete_ticket(1)  # Python client for planfile REST API.
    example_basic_operations(client)
    example_bulk_operations(client)
    example_workflow(client;ticket_id)
    example_error_handling(client)
    main()
  examples/rest-api/05_integration_test.py:
    e: run_tests,TestPlanfileAPI
    TestPlanfileAPI: server(0),client(1),test_health_endpoint(1),test_create_and_get_ticket(1),test_update_ticket(1),test_list_tickets_with_filters(1),test_move_ticket(1)  # Integration tests for planfile REST API.
    run_tests()
  examples/test_litellm_integration.py:
  examples/test_llm_adapters.py:
  examples/test_strategies.py:
    e: validate_strategy_yaml,test_strategy_generation,test_strategy_validation,main
    validate_strategy_yaml(file_path)
    test_strategy_generation(strategy_path)
    test_strategy_validation(strategy_path)
    main()
  mcp-server-example.py:
    e: planfile_generate,planfile_apply,planfile_review,main
    planfile_generate(arguments)
    planfile_apply(arguments)
    planfile_review(arguments)
    main()
  planfile/__init__.py:
    e: quick_ticket,__getattr__,Planfile
    Planfile: __init__(1),auto_discover(2),create_ticket(1),get_ticket(1),list_tickets(0),update_ticket(1),create_tickets_bulk(3)  # Main entry point — convenience wrapper around PlanfileStore.
    quick_ticket(title;tool)
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
    e: list_tickets,create_ticket,get_ticket,update_ticket,delete_ticket,move_ticket,health,TicketCreate,TicketUpdate
    TicketCreate:
    TicketUpdate:
    list_tickets(sprint;status)
    create_ticket(body)
    get_ticket(ticket_id)
    update_ticket(ticket_id;body)
    delete_ticket(ticket_id)
    move_ticket(ticket_id;to_sprint)
    health()
  planfile/builder.py:
    e: create_strategy_command,LLXStrategyBuilder
    LLXStrategyBuilder: __init__(3),_call_llx(1),ask_llm_questions(0),_parse_bullet_list(1),answers_to_strategy(1),build_strategy(1)  # Interactive strategy builder using LLX.
    create_strategy_command(output;model;local)
  planfile/ci.py:
    e: TestResult,BugReport,CIRunner
    TestResult:  # Result of running tests.
    BugReport:  # Generated bug report from test failures.
    CIRunner: __init__(7),run_tests(0),run_code_analysis(0),generate_bug_report(2),create_bug_tickets(1),auto_fix_bugs(1),check_strategy_completion(0),run_loop(0),save_results(2)  # CI/CD runner with automated bug-fix loop and ticket creation
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
    e: github_cmd,gitlab_cmd,jira_cmd,markdown_cmd,all_cmd
    github_cmd(directory;dry_run;direction)
    gitlab_cmd(directory;dry_run;direction)
    jira_cmd(directory;dry_run;direction)
    markdown_cmd(directory;dry_run;direction)
    all_cmd(directory;dry_run;direction)
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
    e: _display_tickets,ticket_create,ticket_list,ticket_show,ticket_update,ticket_move,ticket_import,ticket_done,ticket_start,ticket_block,ticket_review,_parse_checkbox_line,_extract_priority_from_emoji,_check_duplicate_ticket,_import_single_ticket,ticket_import_todo,ticket_export_todo
    _display_tickets(tickets;fmt)
    ticket_create(title;priority;sprint;source;label;description;integration)
    ticket_list(sprint;status;source;label;fmt)
    ticket_show(ticket_id;fmt)
    ticket_update(ticket_id;status;priority;title)
    ticket_move(ticket_id;to_sprint)
    ticket_import(source;sprint;from_file)
    ticket_done(ticket_id)
    ticket_start(ticket_id)
    ticket_block(ticket_id;reason)
    ticket_review(ticket_id)
    _parse_checkbox_line(line)
    _extract_priority_from_emoji(task_text)
    _check_duplicate_ticket(pf;task_text;sprint)
    _import_single_ticket(pf;task_text;priority;sprint;is_checked;todo_file;line_num)
    ticket_import_todo(todo_file;sprint;dry_run)
    ticket_export_todo(todo_file;sprint;include_done)
  planfile/cli/groups/validate/__init__.py:
    e: register_validate_commands
    register_validate_commands(app)
  planfile/cli/groups/validate/commands.py:
    e: validate_strategy_cli
    validate_strategy_cli(strategy_path;verbose)
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
    e: detect_project,get_detected_values
    detect_project(project_path)
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
    e: _find_readme_content,_find_readme_description,_find_readme_goal
    _find_readme_content(project_path)
    _find_readme_description(project_path)
    _find_readme_goal(project_path)
  planfile/cli/project_detector/structure.py:
    e: _analyze_directory_structure
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
    Strategy: get_task_patterns(1),get_sprint(1),validate_sprint_ids(2),compare(1),merge(2),export(1),get_stats(0),to_yaml(0)  # Main strategy configuration - simplified and more flexible.
  planfile/core/models/ticket.py:
    e: TicketSource,Ticket
    TicketSource:  # Who/what created the ticket.
    Ticket: __post_init__(0)  # Atomic unit of work in planfile.
  planfile/core/models.py:
  planfile/core/store.py:
    e: Store
    Store:
  planfile/core/store_files.py:
    e: StoreFileMixin
    StoreFileMixin: _sprint_file(1),_all_sprint_files(0),_read_yaml_cached(1)
  planfile/core/store_tickets.py:
    e: TicketStoreMixin
    TicketStoreMixin: _ticket_from_data(1),_tickets_from_sprint_data(1),_apply_filters(1),list_tickets(1)
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
    e: TicketRef,TicketStatus,PMBackend,BasePMBackend
    TicketRef:  # Reference to a created/updated ticket.
    TicketStatus:  # Status of a ticket.
    PMBackend: create_ticket(1),update_ticket(0),get_ticket(1),list_tickets(0),search_tickets(1)  # Protocol for PM system backends.
    BasePMBackend: __init__(1),_validate_config(0),map_priority(1),prepare_metadata(1),create_ticket(1),_create_ticket(6),update_ticket(7),_update_ticket(7),get_ticket(1),_get_ticket(1),list_tickets(4),_list_tickets(4),search_tickets(1),_search_tickets(1),build_ticket_ref(0),build_ticket_status(0)  # Base class for PM backends with common functionality.
  planfile/sync/generic.py:
    e: GenericBackend
    GenericBackend: __init__(3),_validate_config(0),_make_request(4),_create_ticket(6),_update_ticket(7),_build_update_data(6),_get_ticket(1),_list_tickets(4),_search_tickets(1),_ticket_data_to_status(1)  # Generic HTTP API backend for PM systems.
  planfile/sync/github.py:
    e: GitHubBackend
    GitHubBackend: __init__(2),_validate_config(0),_ensure_labels_exist(1),_create_ticket(7),_update_ticket(8),_get_ticket(1),_issue_to_ticket_status(1),_list_tickets(5),_search_tickets(1)  # GitHub Issues integration backend.
  planfile/sync/gitlab.py:
    e: GitLabBackend
    GitLabBackend: __init__(3),_validate_config(0),_create_ticket(7),_update_ticket(8),_get_ticket(1),_issue_to_ticket_status(1),_list_tickets(5),_search_tickets(1)  # GitLab Issues integration backend.
  planfile/sync/jira.py:
    e: JiraBackend
    JiraBackend: __init__(4),_validate_config(0),map_priority(1),_map_task_type_to_jira(1),_create_ticket(6),_update_ticket(7),_get_ticket(1),_issue_to_ticket_status(1),_list_tickets(4),_search_tickets(1)  # Jira integration backend.
  planfile/sync/markdown_backend/__init__.py:
  planfile/sync/markdown_backend/backend.py:
    e: MarkdownFileBackend
    MarkdownFileBackend: __init__(2),_create_ticket(6)  # Backend for managing tickets in CHANGELOG.md and TODO.md fil
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
  test_chars.py:
  test_checkbox_tickets.py:
    e: test_checkbox_ticket_parsing
    test_checkbox_ticket_parsing()
  test_improvements.py:
    e: test_v2_format,test_backward_compatibility
    test_v2_format()
    test_backward_compatibility()
  test_integration.py:
    e: test_integration
    test_integration()
  test_markdown_integration.py:
    e: test_markdown_backend
    test_markdown_backend()
  test_mixed_format.py:
    e: create_temp_files,categorize_tickets,filter_by_status,filter_by_id_pattern,parse_tickets
    create_temp_files(mixed_content)
    categorize_tickets(tickets)
    filter_by_status(tickets;status)
    filter_by_id_pattern(tickets;pattern)
    parse_tickets(backend)
  test_planfile_final.py:
    e: test_planfile_v2,create_simple_free_strategy
    test_planfile_v2()
    create_simple_free_strategy()
  test_regex.py:
  test_regex2.py:
  test_strategy.py:
    e: test_basic_models,test_yaml_loading
    test_basic_models()
    test_yaml_loading()
  tests/llm_adapters.py:
    e: LLMTestResult,BaseLLMAdapter,LiteLLMAdapter,OpenRouterAdapter,LocalLLMAdapter,LLMTestRunner
    LLMTestResult:  # Result of LLM test.
    BaseLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Base class for LLM adapters.
    LiteLLMAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Adapter for LiteLLM providers.
    OpenRouterAdapter: __init__(1),test_strategy_generation(2),get_available_models(0)  # Adapter for OpenRouter API.
    LocalLLMAdapter: __init__(1),test_strategy_generation(2),_test_ollama(2),_test_openai_compatible(2),get_available_models(0)  # Adapter for local LLM servers (Ollama, LM Studio, etc.).
    LLMTestRunner: __init__(0),register_adapter(2),test_strategy_with_all_adapters(2),generate_report(1),_generate_header(0),_generate_summary_table(1),_generate_detailed_results(1),_generate_successful_tests_section(1),_generate_failed_tests_section(1)  # Run tests across multiple LLM adapters.
  tests/test_strategy.py:
    e: test_placeholder,test_import,test_planfile_bulk_ticket_creation_is_capped,test_sprint_generator_limits_tickets_by_priority
    test_placeholder()
    test_import()
    test_planfile_bulk_ticket_creation_is_capped(monkeypatch)
    test_sprint_generator_limits_tickets_by_priority()
```

## Source Map

*Top 5 modules by symbol density — signatures for LLM orientation.*

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

### `planfile.ci` (`planfile/ci.py`)

```python
class TestResult:  # Result of running tests.
class BugReport:  # Generated bug report from test failures.
class CIRunner:  # CI/CD runner with automated bug-fix loop and ticket creation
    def __init__(strategy_path, project_path, backends, llx_command, max_iterations, auto_fix, planfile_instance)  # CC=4
    def run_tests()  # CC=6
    def run_code_analysis()  # CC=5
    def generate_bug_report(test_result, metrics)  # CC=2
    def create_bug_tickets(bug_report)  # CC=7
    def auto_fix_bugs(bug_report)  # CC=2
    def check_strategy_completion()  # CC=3
    def run_loop()  # CC=7
    def save_results(results, output_path)  # CC=2
```

### `planfile.builder` (`planfile/builder.py`)

```python
def create_strategy_command(output, model, local)  # CC=1, fan=5
class LLXStrategyBuilder:  # Interactive strategy builder using LLX.
    def __init__(llx_path, model, local)  # CC=1
    def _call_llx(prompt)  # CC=3
    def ask_llm_questions()  # CC=4
    def _parse_bullet_list(text)  # CC=4
    def answers_to_strategy(answers)  # CC=3
    def build_strategy(output_path)  # CC=2
```

### `planfile.runner` (`planfile/runner.py`)

```python
def load_valid_strategy(path)  # CC=3, fan=6
def verify_strategy_post_execution(strategy, project_path, backend)  # CC=12, fan=6 ⚠
def _get_project_hash(project_path)  # CC=5, fan=11
def analyze_project_metrics(project_path)  # CC=12, fan=17 ⚠
def apply_strategy_to_tickets(strategy, project_path, backend, dry_run)  # CC=8, fan=3
def review_strategy(strategy, project_path, backends, backend_name)  # CC=14, fan=9 ⚠
def run_strategy(strategy_path, project_path, backend, dry_run)  # CC=8, fan=8
```

### `planfile.examples` (`planfile/examples.py`)

```python
def example_create_strategy()  # CC=1, fan=1
def example_validate_strategy()  # CC=2, fan=3
def example_run_strategy()  # CC=1, fan=1
def example_verify_strategy()  # CC=2, fan=3
def example_programmatic_strategy()  # CC=1, fan=9
```

## Intent

SDLC automation platform - strategic project management with CI/CD integration and automated bug-fix loops
