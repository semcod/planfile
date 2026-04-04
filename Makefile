# Planfile Makefile
.PHONY: help install test docker-build docker-run ci-loop clean

# Default target
help:
	@echo "Planfile CI/CD Automation"
	@echo "============================"
	@echo ""
	@echo "Targets:"
	@echo "  install      Install Planfile with all integrations"
	@echo "  test         Run tests"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run   Run Docker container"
	@echo "  ci-loop      Run CI/CD loop locally"
	@echo "  clean        Clean up artifacts"
	@echo ""
	@echo "Examples:"
	@echo "  make install                    # Install with all backends"
	@echo "  make ci-loop BACKENDS=github    # Run with GitHub only"
	@echo "  make docker-run AUTO_FIX=true   # Run with auto-fix enabled"

# Installation
install:
	pip install -e ".[all]"
	pip install llx

# Testing
test:
	pytest --cov=src --cov-report=html --cov-report=term

# Docker commands
docker-build:
	docker build -t planfile/runner:latest .

docker-run:
	docker-compose up -d planfile-runner
	docker-compose logs -f planfile-runner

docker-stop:
	docker-compose down

docker-clean:
	docker-compose down -v
	docker system prune -f

# CI/CD commands
ci-loop:
	@if [ -z "$(STRATEGY)" ]; then \
		echo "Usage: make ci-loop STRATEGY=<strategy.yaml> [BACKENDS=github,jira] [MAX_ITERATIONS=5]"; \
		exit 1; \
	fi
	planfile auto loop \
		--strategy $(STRATEGY) \
		--project . \
		--backend $(or $(BACKENDS),github) \
		--max-iterations $(or $(MAX_ITERATIONS),5) \
		$(if $(filter true,$(AUTO_FIX)),--auto-fix) \
		--output ci-results.json

# Development commands
dev-setup:
	python -m venv .venv
	source .venv/bin/activate && pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

# Examples
example-github:
	@echo "Running example with GitHub backend..."
	@echo "Make sure GITHUB_TOKEN and GITHUB_REPO are set"
	planfile auto loop \
		--strategy examples/strategies/onboarding.yaml \
		--project . \
		--backend github \
		--max-iterations 3 \
		--dry-run

example-jira:
	@echo "Running example with Jira backend..."
	@echo "Make sure JIRA_URL, JIRA_EMAIL, JIRA_TOKEN, JIRA_PROJECT are set"
	planfile auto loop \
		--strategy examples/strategies/ecommerce-mvp.yaml \
		--project . \
		--backend jira \
		--max-iterations 3 \
		--dry-run

# Monitoring
status:
	planfile auto ci-status

logs:
	docker-compose logs -f planfile-runner

# Cleanup
clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.json
	rm -rf ci-results.json
	rm -rf test-results.xml
	rm -rf build
	rm -rf dist
	rm -rf *.egg-info

# Release
version:
	@python -c "import planfile; print(planfile.__version__)"

bump-patch:
	bump2version patch

bump-minor:
	bump2version minor

bump-major:
	bump2version major

publish:
	python3 -m build
	twine upload dist/*

# CI/CD Pipeline helpers
pipeline-test:
	@echo "Running full CI/CD pipeline locally..."
	@echo "Step 1: Install dependencies"
	make install
	@echo "Step 2: Run tests"
	make test
	@echo "Step 3: Run CI loop"
	make ci-loop STRATEGY=examples/strategies/onboarding.yaml BACKENDS=github MAX_ITERATIONS=1

pipeline-docker:
	@echo "Running CI/CD pipeline in Docker..."
	make docker-build
	docker-compose up -d
	sleep 10
	docker-compose exec planfile-runner planfile auto loop \
		--strategy /app/planfile.yaml \
		--project /workspace \
		--backend github \
		--max-iterations 1

# Advanced examples
full-loop:
	@echo "Running full bug-fix loop with auto-fix..."
	planfile auto loop \
		--strategy examples/strategies/onboarding.yaml \
		--project . \
		--backend github \
		--max-iterations 10 \
		--auto-fix \
		--output full-loop-results.json

strategy-review:
	planfile strategy review \
		--strategy examples/strategies/onboarding.yaml \
		--project . \
		--backend github

# Integration tests
test-github:
	@echo "Testing GitHub integration..."
	@if [ -z "$(GITHUB_TOKEN)" ] || [ -z "$(GITHUB_REPO)" ]; then \
		echo "Set GITHUB_TOKEN and GITHUB_REPO"; \
		exit 1; \
	fi
	python3 -m tests.integration.test_github

test-jira:
	@echo "Testing Jira integration..."
	@if [ -z "$(JIRA_TOKEN)" ] || [ -z "$(JIRA_URL)" ]; then \
		echo "Set JIRA_TOKEN and JIRA_URL"; \
		exit 1; \
	fi
	python -m tests.integration.test_jira

# Documentation
docs:
	@echo "Generating documentation..."
	cd docs && make html

serve-docs:
	@echo "Serving documentation..."
	cd docs/_build/html && python3 -m http.server 8080

# Quick start
quick-start:
	@echo "Quick start with Planfile"
	@echo "=========================="
	@echo "1. Install: make install"
	@echo "2. Configure: export GITHUB_TOKEN=your_token"
	@echo "3. Run: make ci-loop STRATEGY=examples/strategies/onboarding.yaml"
	@echo ""
	@echo "For Docker: make docker-build && make docker-run"
