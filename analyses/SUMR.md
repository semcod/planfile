# Planfile

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Quality Pipeline (`pyqual.yaml`)](#quality-pipeline-pyqualyaml)
- [Dependencies](#dependencies)
- [Source Map](#source-map)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `planfile`
- **version**: `0.1.59`
- **python_requires**: `>=3.10`
- **license**: Apache-2.0
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Taskfile.yml, Makefile, app.doql.css, pyqual.yaml, goal.yaml, Dockerfile, docker-compose.yml, src(8 mod), project/(5 analysis files)

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

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 174f 17980L | python:136,shell:37,javascript:1 | 2026-04-19
# CC̄=3.5 | critical:8/644 | dups:3 | cycles:0

HEALTH[9]:
  🔴 DUP   3 classes duplicated
  🟡 CC    demo_checkbox_tickets CC=15 (limit:15)
  🟡 CC    _find_readme_content CC=16 (limit:15)
  🟡 CC    get_detected_values CC=15 (limit:15)
  🟡 CC    _analyze_directory_structure CC=20 (limit:15)
  🟡 CC    _infer_python_project_type CC=17 (limit:15)
  🟡 CC    _create_ticket CC=15 (limit:15)
  🟡 CC    _update_ticket CC=15 (limit:15)
  🟡 CC    get_stats CC=15 (limit:15)

REFACTOR[2]:
  1. rm duplicates  (-3 dup classes)
  2. split 8 high-CC methods  (CC>15)

PIPELINES[329]:
  [1] Src [BASE_URL]: BASE_URL → request
      PURITY: 100% pure
  [2] Src [url]: url
      PURITY: 100% pure
  [3] Src [response]: response
      PURITY: 100% pure
  [4] Src [client]: client → health → createTicket → request
      PURITY: 100% pure
  [5] Src [ticket]: ticket → createTicket → request
      PURITY: 100% pure

LAYERS:
  planfile/                       CC̄=4.0    ←in:43  →out:33  !! split  ×DUP
  │ runner                     418L  0C    7m  CC=14     ←4
  │ generator                  347L  1C   24m  CC=14     ←0
  │ executor_standalone        338L  3C   12m  CC=8      ←0
  │ yaml_loader                331L  0C   15m  CC=7      ←7
  │ ci                         315L  3C    9m  CC=7      ←0
  │ commands                   293L  0C   17m  CC=14     ←0
  │ jira                       280L  1C   10m  CC=13     ←0
  │ external_tools             268L  2C   12m  CC=12     ←0
  │ !! strategy                   260L  6C   12m  CC=15     ←0
  │ operations                 259L  0C   15m  CC=9      ←1
  │ core                       256L  0C   11m  CC=9      ←1
  │ commands                   244L  0C    8m  CC=10     ←0
  │ !! github                     240L  1C    9m  CC=15     ←0
  │ base                       236L  4C   21m  CC=4      ←0
  │ commands                   235L  0C    8m  CC=10     ←0
  │ !! gitlab                     233L  1C    8m  CC=15     ←0
  │ metrics                    227L  0C    5m  CC=8      ←0
  │ redup_importer             221L  0C    5m  CC=11     ←1
  │ commands                   218L  0C   11m  CC=11     ←0
  │ generic                    216L  1C   10m  CC=6      ←0
  │ server                     209L  0C    4m  CC=14     ←0
  │ sprint_generator           206L  1C   10m  CC=9      ←0
  │ config                     206L  1C   14m  CC=10     ←0
  │ commands                   197L  0C    3m  CC=13     ←1
  │ cli_loader                 194L  0C   10m  CC=7      ←0
  │ toon_parser                189L  0C    7m  CC=11     ←2
  │ gates                      170L  0C   13m  CC=8      ←3
  │ __init__                   167L  1C    9m  CC=11     ←10
  │ mock                       160L  1C    6m  CC=11     ←0
  │ generator                  145L  0C    6m  CC=8      ←1
  │ examples                   139L  0C    5m  CC=2      ←0
  │ commands                   132L  0C    2m  CC=14     ←0
  │ code2llm_importer          129L  1C    9m  CC=13     ←1
  │ file_analyzer              127L  1C   10m  CC=9      ←0
  │ yaml_parser                123L  0C    7m  CC=5      ←2
  │ commands                   119L  0C    4m  CC=6      ←0
  │ text_parser                118L  0C    1m  CC=13     ←3
  │ pyproject                  117L  0C    9m  CC=8      ←1
  │ priorities                 111L  0C    3m  CC=4      ←0
  │ tickets                    110L  1C    6m  CC=12     ←0
  │ utils                      108L  0C    5m  CC=7      ←1
  │ __init__                   104L  1C    5m  CC=3      ←0  ×DUP
  │ commands                   100L  0C    1m  CC=10     ←0
  │ server                      97L  2C    7m  CC=4      ←0
  │ vallm_importer              96L  1C   10m  CC=4      ←1
  │ !! main                        88L  0C    2m  CC=15     ←1
  │ !! inference                   87L  0C    3m  CC=17     ←2
  │ utils                       86L  0C    3m  CC=7      ←1
  │ commands                    78L  0C    1m  CC=1      ←1
  │ adapters                    75L  6C    5m  CC=1      ←0
  │ commands                    73L  0C    5m  CC=4      ←0
  │ package                     73L  0C    1m  CC=7      ←1
  │ !! readme                      71L  0C    3m  CC=16     ←3
  │ registry                    67L  1C    5m  CC=2      ←6
  │ fallback                    66L  0C    1m  CC=9      ←1
  │ prompts                     63L  0C    1m  CC=5      ←1
  │ client                      63L  0C    1m  CC=4      ←1
  │ __init__                    63L  0C    0m  CC=0.0    ←0
  │ model_tier                  60L  0C    4m  CC=9      ←3
  │ !! structure                   60L  0C    1m  CC=20     ←3
  │ commands                    59L  0C    3m  CC=2      ←0
  │ store_tickets               54L  1C    4m  CC=7      ←0
  │ ticket                      51L  2C    1m  CC=2      ←0
  │ backend                     50L  1C    2m  CC=2      ←0
  │ state                       46L  1C    5m  CC=3      ←0
  │ base                        46L  3C    0m  CC=0.0    ←0
  │ metrics_extractor           44L  0C    6m  CC=9      ←1
  │ commands                    42L  0C    1m  CC=9      ←0
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
  │ extra_commands              20L  0C    1m  CC=1      ←0
  │ __init__                    18L  0C    1m  CC=1      ←0
  │ __init__                    18L  0C    1m  CC=1      ←0
  │ __init__                    18L  0C    1m  CC=1      ←0
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
  │ __init__                    11L  0C    1m  CC=1      ←0
  │ store                       11L  1C    0m  CC=0.0    ←0
  │ execution                    6L  0C    0m  CC=0.0    ←0
  │ constants                    5L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ __main__                     4L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ gitlab                       1L  0C    0m  CC=0.0    ←0
  │ github                       1L  0C    0m  CC=0.0    ←0
  │ generic                      1L  0C    0m  CC=0.0    ←0
  │ base                         1L  0C    0m  CC=0.0    ←0
  │ jira                         1L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │
  examples/                       CC̄=2.0    ←in:0  →out:2  ×DUP
  │ !! 04_llx_integration         503L  2C    9m  CC=12     ←1
  │ 02_mcp_integration         381L  0C    6m  CC=9      ←0
  │ 03_proxy_routing           368L  1C    7m  CC=8      ←0
  │ 01_full_workflow.sh        352L  4C   12m  CC=0.0    ←0
  │ test_interactive_expect.sh   278L  0C    0m  CC=0.0    ←0
  │ test_planfile_generation.sh   277L  4C    7m  CC=0.0    ←0
  │ 03_python_client           250L  1C   14m  CC=4      ←0
  │ verify_planfile.sh         245L  0C    2m  CC=0.0    ←0
  │ 03_integration             218L  1C    9m  CC=4      ←0  ×DUP
  │ PROPOSED_API_IMPROVEMENTS   217L  2C    7m  CC=13     ←0  ×DUP
  │ run_all_tests.sh           203L  0C    2m  CC=0.0    ←0
  │ llx_validator              185L  1C    7m  CC=4      ←0
  │ 02_ticket_management       172L  0C    6m  CC=3      ←0
  │ run.sh                     166L  0C    1m  CC=0.0    ←0
  │ 04_advanced_filtering      161L  0C    6m  CC=12     ←0
  │ test_readme_examples.sh    158L  1C    3m  CC=0.0    ←0
  │ 04_javascript_client.js    152L  1C   18m  CC=5      ←0
  │ run.sh                     129L  0C    0m  CC=0.0    ←0
  │ run.sh                     128L  0C    0m  CC=0.0    ←0
  │ 01_basic_usage             112L  0C    5m  CC=3      ←0
  │ !! demo                       109L  0C    1m  CC=15     ←0
  │ run.sh                     109L  0C    0m  CC=0.0    ←0
  │ 02_curl_examples.sh        102L  0C    2m  CC=0.0    ←0
  │ run.sh                      92L  0C    1m  CC=0.0    ←0
  │ run.sh                      92L  0C    1m  CC=0.0    ←0
  │ run.sh                      89L  0C    1m  CC=0.0    ←20
  │ validate_with_llx.sh        65L  0C    1m  CC=0.0    ←0
  │ 04_analytics_simple         59L  0C    1m  CC=1      ←0
  │ 03_integration_simple       52L  0C    1m  CC=3      ←0
  │ run_all.sh                  49L  0C    1m  CC=0.0    ←0
  │ 01_start_server.sh          47L  0C    0m  CC=0.0    ←0
  │ run_fixed.sh                47L  0C    0m  CC=0.0    ←0
  │ run.sh                      40L  0C    0m  CC=0.0    ←0
  │ run.sh                      38L  0C    0m  CC=0.0    ←0
  │ run_fixed.sh                35L  0C    0m  CC=0.0    ←0
  │ run.sh                      34L  0C    0m  CC=0.0    ←0
  │ run_all.sh                  30L  0C    0m  CC=0.0    ←0
  │ run.sh                      29L  0C    0m  CC=0.0    ←0
  │ run.sh                      29L  0C    0m  CC=0.0    ←0
  │ run.sh                      29L  0C    0m  CC=0.0    ←0
  │ run.sh                      17L  0C    0m  CC=0.0    ←0
  │ ci-workflow.sh              16L  0C    0m  CC=0.0    ←0
  │ run.sh                      13L  0C    0m  CC=0.0    ←0
  │ run.sh                      13L  0C    0m  CC=0.0    ←0
  │ run.sh                      12L  0C    0m  CC=0.0    ←0
  │ planfile-sync.sh            10L  0C    0m  CC=0.0    ←0
  │
  ./                              CC̄=0.2    ←in:0  →out:0
  │ run_examples.sh            286L  0C   13m  CC=0.0    ←7
  │ docker-entrypoint.sh       174L  0C    5m  CC=0.0    ←0
  │ auto_generate_planfile.sh   124L  0C    0m  CC=0.0    ←0
  │ cleanup_redundant.sh        71L  0C    0m  CC=0.0    ←0
  │ project.sh                  40L  0C    0m  CC=0.0    ←0
  │ mcp-server-example          28L  0C    4m  CC=1      ←0
  │
  ── zero ──
     planfile/cli/__init__.py                  0L
     planfile/loaders/__init__.py              0L
     planfile/utils/__init__.py                0L

COUPLING:
                           examples.gitlab  examples.python-api   examples.ecosystem             planfile         planfile.cli    examples.rest-api    planfile.analysis     planfile.loaders         run_examples        planfile.sync         planfile.api   planfile.importers         planfile.llm             examples        planfile.core
      examples.gitlab                   ──                 ←145                  ←95                  ←27                                       ←29                  ←15                   ←2                                        ←6                                                             ←1                   ←1                   ←2  hub
  examples.python-api                  145                   ──                                        20                                                                                                                                                                                                                                         !! fan-out
   examples.ecosystem                   95                                        ──                                                                                                                                                                                                                ←2                                            !! fan-out
             planfile                   27                  ←20                                        ──                  ←15                                                              1                                                             ←6                    5                                        ←1                       hub
         planfile.cli                                                                                  15                   ──                                                             12                   15                    2                                                              1                                            !! fan-out
    examples.rest-api                   29                                                                                                       ──                                                                                                                                                                                               !! fan-out
    planfile.analysis                   15                                                                                                                            ──                                                                                                                                                                          !! fan-out
     planfile.loaders                    2                                                             ←1                  ←12                                                             ──                                                                                                                                                     hub
         run_examples                                                                                                      ←15                                                                                  ──                                                                                                                                hub
        planfile.sync                    6                                                                                  ←2                                                                                                       ──                                                                                                         
         planfile.api                                                                                   6                                                                                                                                                 ──                                                                                    
   planfile.importers                                                                                  ←5                                                                                                                                                                      ──                                                                 hub
         planfile.llm                    1                                         2                                        ←1                                                                                                                                                                      ──                                          
             examples                    1                                                              1                                                                                                                                                                                                                ──                     
        planfile.core                    2                                                                                                                                                                                                                                                                                                    ──
  CYCLES: none
  HUB: planfile.loaders/ (fan-in=13)
  HUB: planfile.importers/ (fan-in=5)
  HUB: planfile/ (fan-in=43)
  HUB: run_examples/ (fan-in=15)
  HUB: examples.gitlab/ (fan-in=323)
  SMELL: examples.ecosystem/ fan-out=95 → split needed
  SMELL: planfile.analysis/ fan-out=15 → split needed
  SMELL: planfile/ fan-out=33 → split needed
  SMELL: examples.python-api/ fan-out=165 → split needed
  SMELL: examples.rest-api/ fan-out=29 → split needed
  SMELL: planfile.cli/ fan-out=45 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 12 groups | 135f 14020L | 2026-04-19

SUMMARY:
  files_scanned: 135
  total_lines:   14020
  dup_groups:    12
  dup_fragments: 34
  saved_lines:   131
  scan_ms:       6741

HOTSPOTS[7] (files with most duplication):
  planfile/cli/project_detector/gates.py  dup=32L  groups=2  frags=4  (0.2%)
  planfile/cli/groups/sync/commands.py  dup=28L  groups=1  frags=4  (0.2%)
  planfile/cli/groups/ticket/commands.py  dup=27L  groups=1  frags=3  (0.2%)
  planfile/cli/groups/sync/core.py  dup=24L  groups=1  frags=2  (0.2%)
  planfile/cli/core/console.py  dup=15L  groups=1  frags=5  (0.1%)
  planfile/sync/base.py  dup=14L  groups=1  frags=1  (0.1%)
  planfile/sync/jira.py  dup=14L  groups=1  frags=1  (0.1%)

DUPLICATES[12] (ranked by impact):
  [73f23dc09aac9b7a]   STRU  github_cmd  L=7 N=4 saved=21 sim=1.00
      planfile/cli/groups/sync/commands.py:11-17  (github_cmd)
      planfile/cli/groups/sync/commands.py:20-26  (gitlab_cmd)
      planfile/cli/groups/sync/commands.py:29-35  (jira_cmd)
      planfile/cli/groups/sync/commands.py:38-44  (markdown_cmd)
  [743611597bf1e270]   STRU  ticket_done  L=9 N=3 saved=18 sim=1.00
      planfile/cli/groups/ticket/commands.py:127-135  (ticket_done)
      planfile/cli/groups/ticket/commands.py:137-145  (ticket_start)
      planfile/cli/groups/ticket/commands.py:160-168  (ticket_review)
  [84118158d8b5d9f1]   STRU  register_apply_commands  L=3 N=6 saved=15 sim=1.00
      planfile/cli/groups/apply/__init__.py:9-11  (register_apply_commands)
      planfile/cli/groups/examples/__init__.py:9-11  (register_examples_commands)
      planfile/cli/groups/health/__init__.py:9-11  (register_health_commands)
      planfile/cli/groups/init/__init__.py:9-11  (register_init_commands)
      planfile/cli/groups/review/__init__.py:9-11  (register_review_commands)
      planfile/cli/groups/validate/__init__.py:9-11  (register_validate_commands)
  [f071e098e43958d3]   STRU  map_priority  L=14 N=2 saved=14 sim=1.00
      planfile/sync/base.py:66-79  (map_priority)
      planfile/sync/jira.py:65-78  (map_priority)
  [21eb3398cdd6a2b6]   STRU  print_success  L=3 N=5 saved=12 sim=1.00
      planfile/cli/core/console.py:9-11  (print_success)
      planfile/cli/core/console.py:14-16  (print_error)
      planfile/cli/core/console.py:19-21  (print_warning)
      planfile/cli/core/console.py:24-26  (print_info)
      planfile/cli/core/console.py:29-31  (print_dim)
  [6a6c4ffd98c596b0]   STRU  _collect_tickets_from_sprint  L=12 N=2 saved=12 sim=1.00
      planfile/cli/groups/sync/core.py:58-69  (_collect_tickets_from_sprint)
      planfile/cli/groups/sync/core.py:72-83  (_collect_tickets_from_backlog)
  [1d3d96e641f80678]   STRU  _detect_docker_gates  L=9 N=2 saved=9 sim=1.00
      planfile/cli/project_detector/gates.py:40-48  (_detect_docker_gates)
      planfile/cli/project_detector/gates.py:145-153  (_detect_doc_gates)
  [647474f57d8a2dab]   STRU  register_auto_commands  L=8 N=2 saved=8 sim=1.00
      planfile/cli/groups/auto/__init__.py:11-18  (register_auto_commands)
      planfile/cli/groups/generate/__init__.py:11-18  (register_generate_commands)
  [9c4f9ae7fbca56f4]   STRU  _has_mypy_config  L=7 N=2 saved=7 sim=1.00
      planfile/cli/project_detector/gates.py:103-109  (_has_mypy_config)
      planfile/cli/project_detector/gates.py:136-142  (_has_bandit_config)
  [ea2851389f454151]   STRU  import_json  L=7 N=2 saved=7 sim=1.00
      planfile/importers/json_importer.py:8-14  (import_json)
      planfile/importers/yaml_importer.py:8-14  (import_yaml)
  [1aa5c925a5a0c66c]   EXAC  __init__  L=4 N=2 saved=4 sim=1.00
      examples/PROPOSED_API_IMPROVEMENTS.py:27-30  (__init__)
      planfile/extensions/__init__.py:29-32  (__init__)
  [3252487e1015a40a]   STRU  _find_readme_description  L=4 N=2 saved=4 sim=1.00
      planfile/cli/project_detector/readme.py:62-65  (_find_readme_description)
      planfile/cli/project_detector/readme.py:68-71  (_find_readme_goal)

REFACTOR[12] (ranked by priority):
  [1] ○ extract_function   → planfile/cli/groups/sync/utils/github_cmd.py
      WHY: 4 occurrences of 7-line block across 1 files — saves 21 lines
      FILES: planfile/cli/groups/sync/commands.py
  [2] ○ extract_function   → planfile/cli/groups/ticket/utils/ticket_done.py
      WHY: 3 occurrences of 9-line block across 1 files — saves 18 lines
      FILES: planfile/cli/groups/ticket/commands.py
  [3] ○ extract_function   → planfile/cli/groups/utils/register_apply_commands.py
      WHY: 6 occurrences of 3-line block across 6 files — saves 15 lines
      FILES: planfile/cli/groups/apply/__init__.py, planfile/cli/groups/examples/__init__.py, planfile/cli/groups/health/__init__.py, planfile/cli/groups/init/__init__.py, planfile/cli/groups/review/__init__.py +1 more
  [4] ○ extract_function   → planfile/sync/utils/map_priority.py
      WHY: 2 occurrences of 14-line block across 2 files — saves 14 lines
      FILES: planfile/sync/base.py, planfile/sync/jira.py
  [5] ○ extract_function   → planfile/cli/core/utils/print_success.py
      WHY: 5 occurrences of 3-line block across 1 files — saves 12 lines
      FILES: planfile/cli/core/console.py
  [6] ○ extract_function   → planfile/cli/groups/sync/utils/_collect_tickets_from_sprint.py
      WHY: 2 occurrences of 12-line block across 1 files — saves 12 lines
      FILES: planfile/cli/groups/sync/core.py
  [7] ○ extract_function   → planfile/cli/project_detector/utils/_detect_docker_gates.py
      WHY: 2 occurrences of 9-line block across 1 files — saves 9 lines
      FILES: planfile/cli/project_detector/gates.py
  [8] ○ extract_function   → planfile/cli/groups/utils/register_auto_commands.py
      WHY: 2 occurrences of 8-line block across 2 files — saves 8 lines
      FILES: planfile/cli/groups/auto/__init__.py, planfile/cli/groups/generate/__init__.py
  [9] ○ extract_function   → planfile/cli/project_detector/utils/_has_mypy_config.py
      WHY: 2 occurrences of 7-line block across 1 files — saves 7 lines
      FILES: planfile/cli/project_detector/gates.py
  [10] ○ extract_function   → planfile/importers/utils/import_json.py
      WHY: 2 occurrences of 7-line block across 2 files — saves 7 lines
      FILES: planfile/importers/json_importer.py, planfile/importers/yaml_importer.py
  [11] ○ extract_class      → utils/__init__.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: examples/PROPOSED_API_IMPROVEMENTS.py, planfile/extensions/__init__.py
  [12] ○ extract_function   → planfile/cli/project_detector/utils/_find_readme_description.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: planfile/cli/project_detector/readme.py

QUICK_WINS[10] (low risk, high savings — do first):
  [1] extract_function   saved=21L  → planfile/cli/groups/sync/utils/github_cmd.py
      FILES: commands.py
  [2] extract_function   saved=18L  → planfile/cli/groups/ticket/utils/ticket_done.py
      FILES: commands.py
  [3] extract_function   saved=15L  → planfile/cli/groups/utils/register_apply_commands.py
      FILES: __init__.py, __init__.py, __init__.py +3
  [4] extract_function   saved=14L  → planfile/sync/utils/map_priority.py
      FILES: base.py, jira.py
  [5] extract_function   saved=12L  → planfile/cli/core/utils/print_success.py
      FILES: console.py
  [6] extract_function   saved=12L  → planfile/cli/groups/sync/utils/_collect_tickets_from_sprint.py
      FILES: core.py
  [7] extract_function   saved=9L  → planfile/cli/project_detector/utils/_detect_docker_gates.py
      FILES: gates.py
  [8] extract_function   saved=8L  → planfile/cli/groups/utils/register_auto_commands.py
      FILES: __init__.py, __init__.py
  [9] extract_function   saved=7L  → planfile/cli/project_detector/utils/_has_mypy_config.py
      FILES: gates.py
  [10] extract_function   saved=7L  → planfile/importers/utils/import_json.py
      FILES: json_importer.py, yaml_importer.py

DEPENDENCY_RISK[1] (duplicates spanning multiple packages):
  __init__  packages=2  files=2
      examples/PROPOSED_API_IMPROVEMENTS.py
      planfile/extensions/__init__.py

EFFORT_ESTIMATE (total ≈ 4.5h):
  medium github_cmd                          saved=21L  ~42min
  medium ticket_done                         saved=18L  ~36min
  medium register_apply_commands             saved=15L  ~30min
  easy   map_priority                        saved=14L  ~28min
  easy   print_success                       saved=12L  ~24min
  easy   _collect_tickets_from_sprint        saved=12L  ~24min
  easy   _detect_docker_gates                saved=9L  ~18min
  easy   register_auto_commands              saved=8L  ~16min
  easy   _has_mypy_config                    saved=7L  ~14min
  easy   import_json                         saved=7L  ~14min
  ... +2 more (~24min)

METRICS-TARGET:
  dup_groups:  12 → 0
  saved_lines: 131 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 509 func | 94f | 2026-04-19

NEXT[5] (ranked by impact):
  [1] !  SPLIT-FUNC      _analyze_directory_structure  CC=20  fan=9
      WHY: CC=20 exceeds 15
      EFFORT: ~1h  IMPACT: 180

  [2] !  SPLIT-FUNC      _find_readme_content  CC=16  fan=10
      WHY: CC=16 exceeds 15
      EFFORT: ~1h  IMPACT: 160

  [3] !  SPLIT-FUNC      _infer_python_project_type  CC=17  fan=8
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 136

  [4] !  SPLIT-FUNC      Strategy.get_stats  CC=15  fan=9
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 135

  [5] !  SPLIT-FUNC      GitHubBackend._create_ticket  CC=15  fan=8
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 120


RISKS[0]: none

METRICS-TARGET:
  CC̄:          3.8 → ≤2.7
  max-CC:      20 → ≤10
  god-modules: 0 → 0
  high-CC(≥15): 7 → ≤3
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
  prev CC̄=3.8 → now CC̄=3.8
```

### Validation (`project/validation.toon.yaml`)

```toon markpact:analysis path=project/validation.toon.yaml
# vallm batch | 360f | 269✓ 11⚠ 6✗ | 2026-04-13

SUMMARY:
  scanned: 360  passed: 269 (74.7%)  warnings: 11  errors: 6  unsupported: 85

WARNINGS[11]{path,score}:
  examples/advanced-usage/final-strategy.yaml,0.97
    issues[1]{rule,severity,message,line}:
      complexity.lizard_length,warning,_report: 287 lines exceeds limit 100,137
  examples/bash-generation/verify_planfile.sh,0.97
    issues[1]{rule,severity,message,line}:
      complexity.lizard_cc,warning,validate_planfile: CC=17 exceeds limit 15,11
  examples/ecosystem/04_llx_integration.py,0.97
    issues[1]{rule,severity,message,line}:
      complexity.lizard_length,warning,example_metric_driven_planning: 175 lines exceeds limit 100,188
  examples/validate_with_llx.sh,0.97
    issues[1]{rule,severity,message,line}:
      complexity.lizard_cc,warning,validate_file: CC=17 exceeds limit 15,18
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
  run_examples.sh,0.97
    issues[1]{rule,severity,message,line}:
      complexity.lizard_length,warning,setup_environment: 141 lines exceeds limit 100,109
  planfile/core/models/strategy.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.maintainability,warning,Low maintainability index: 16.2 (threshold: 20),
  test_checkbox_tickets.py,0.98
    issues[1]{rule,severity,message,line}:
      complexity.cyclomatic,warning,test_checkbox_ticket_parsing has cyclomatic complexity 16 (max: 15),8

ERRORS[6]{path,score}:
  examples/llm-integration/llm-config.yaml,0.00
    issues[1]{rule,severity,message,line}:
      syntax.tree_sitter,error,tree-sitter found 1 parse error(s) in yaml,
  examples/test_litellm_integration.py,0.00
    issues[1]{rule,severity,message,line}:
      syntax.parse,error,SyntaxError: expected an indented block after 'if' statement on line 297,298
  examples/test_llm_adapters.py,0.00
    issues[1]{rule,severity,message,line}:
      syntax.parse,error,SyntaxError: unexpected indent,25
  test-integrated.yaml,0.00
    issues[1]{rule,severity,message,line}:
      syntax.tree_sitter,error,tree-sitter found 1 parse error(s) in yaml,
  planfile/examples.py,0.64
    issues[5]{rule,severity,message,line}:
      python.import.resolvable,error,Module 'llx.planfile' not found,10
      python.import.resolvable,error,Module 'llx.planfile' not found,23
      python.import.resolvable,error,Module 'llx.planfile' not found,36
      python.import.resolvable,error,Module 'llx.planfile' not found,49
      python.import.resolvable,error,Module 'llx.planfile.models' not found,67
  mcp-server-example.py,0.79
    issues[2]{rule,severity,message,line}:
      python.import.resolvable,error,Module 'mcp.server' not found,3
      python.import.resolvable,error,Module 'mcp.server.stdio' not found,4

UNSUPPORTED[6]{bucket,count}:
  *.md,50
  Dockerfile*,1
  *.txt,2
  *.yml,2
  *.example,4
  other,26
```

## Intent

SDLC automation platform - strategic project management with CI/CD integration and automated bug-fix loops
