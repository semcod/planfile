# Planfile Examples

Real-world examples and templates for different project types and use cases.

## Project Templates

### Web Application Strategy

```yaml
name: "E-commerce Platform"
project_type: "web"
domain: "ecommerce"
goal: "Launch a full-featured e-commerce platform with payment processing"

sprints:
  - id: 1
    name: "Foundation & Setup"
    length_days: 14
    objectives:
      - Set up project structure and CI/CD
      - Implement user authentication
      - Create database schema
    tasks:
      - type: "feature"
        title: "Setup project structure"
        description: "Create basic project layout with React frontend and Node.js backend"
        estimate: 2
        priority: "high"
        quality_criteria:
          - "ESLint configuration"
          - "Prettier setup"
          - "Git hooks configured"
      
      - type: "feature"
        title: "Implement user authentication"
        description: "Add JWT-based authentication with registration and login"
        estimate: 4
        priority: "high"
        dependencies:
          - "database_setup"
        quality_criteria:
          - "Unit tests for auth flows"
          - "Security review completed"
      
      - type: "feature"
        title: "Database schema design"
        description: "Design and implement PostgreSQL schema for users, products, orders"
        estimate: 3
        priority: "high"
        quality_criteria:
          - "Migration scripts"
          - "Database indexes optimized"
          - "Backup strategy defined"

    quality_gates:
      - name: "Code Coverage"
        type: "coverage"
        threshold: 80
      - name: "Security Scan"
        type: "security"
        threshold: "no_critical"

  - id: 2
    name: "Core Features"
    length_days: 21
    objectives:
      - Implement product catalog
      - Add shopping cart functionality
      - Integrate payment gateway
    tasks:
      - type: "feature"
        title: "Product catalog API"
        description: "RESTful API for product management with search and filtering"
        estimate: 5
        priority: "high"
        dependencies:
          - "database_setup"
      
      - type: "feature"
        title: "Shopping cart implementation"
        description: "Client-side shopping cart with localStorage persistence"
        estimate: 4
        priority: "high"
      
      - type: "feature"
        title: "Payment gateway integration"
        description: "Stripe integration for payment processing"
        estimate: 6
        priority: "critical"
        dependencies:
          - "shopping_cart"
        quality_criteria:
          - "PCI compliance check"
          - "Webhook handling implemented"
          - "Error handling for payment failures"

success_metrics:
  - metric: "User registration conversion rate"
    target: "> 15%"
  - metric: "Checkout completion rate"
    target: "> 60%"
  - metric: "Page load time"
    target: "< 2 seconds"
```

### Mobile App Strategy

```yaml
name: "Health Tracking Mobile App"
project_type: "mobile"
domain: "healthcare"
goal: "Launch a cross-platform health tracking app with data synchronization"

sprints:
  - id: 1
    name: "Core Architecture"
    length_days: 10
    objectives:
      - Set up React Native project
      - Implement navigation structure
      - Create data models
    tasks:
      - type: "feature"
        title: "React Native setup"
        description: "Initialize React Native project with TypeScript and navigation"
        estimate: 2
        priority: "high"
      
      - type: "feature"
        title: "Navigation implementation"
        description: "Set up React Navigation with tab and stack navigators"
        estimate: 3
        priority: "high"
      
      - type: "feature"
        title: "Health data models"
        description: "Create TypeScript interfaces for health metrics and user data"
        estimate: 2
        priority: "medium"

  - id: 2
    name: "Health Tracking Features"
    length_days: 14
    objectives:
      - Implement step tracking
      - Add heart rate monitoring
      - Create data visualization
    tasks:
      - type: "feature"
        title: "Step counter integration"
        description: "Integrate with device pedometer and display daily steps"
        estimate: 4
        priority: "high"
      
      - type: "feature"
        title: "Heart rate monitoring"
        description: "Connect to heart rate sensors and display real-time data"
        estimate: 5
        priority: "high"
      
      - type: "feature"
        title: "Data visualization charts"
        description: "Implement charts for health trends using react-native-svg-charts"
        estimate: 4
        priority: "medium"

quality_gates:
  - name: "App Performance"
    type: "performance"
    threshold: "startup_time < 3s"
  - name: "Crash Rate"
    type: "stability"
    threshold: "< 1%"

success_metrics:
  - metric: "Daily active users"
    target: "> 1000"
  - metric: "Data points per day"
    target: "> 10,000"
  - metric: "App store rating"
    target: "> 4.5 stars"
```

### API Service Strategy

```yaml
name: "Microservices API Platform"
project_type: "api"
domain: "fintech"
goal: "Build scalable microservices API with comprehensive monitoring"

sprints:
  - id: 1
    name: "API Foundation"
    length_days: 14
    objectives:
      - Set up microservices architecture
      - Implement authentication service
      - Create API documentation
    tasks:
      - type: "feature"
        title: "Microservices setup"
        description: "Docker-based microservices with service discovery"
        estimate: 4
        priority: "high"
      
      - type: "feature"
        title: "Authentication service"
        description: "OAuth2/JWT authentication service with user management"
        estimate: 5
        priority: "critical"
      
      - type: "feature"
        title: "API documentation"
        description: "OpenAPI 3.0 specification with Swagger UI"
        estimate: 3
        priority: "medium"

  - id: 2
    name: "Core Services"
    length_days: 21
    objectives:
      - Implement user service
      - Add transaction service
      - Create notification service
    tasks:
      - type: "feature"
        title: "User management service"
        description: "CRUD operations for user profiles and preferences"
        estimate: 6
        priority: "high"
      
      - type: "feature"
        title: "Transaction processing"
        description: "Financial transaction processing with audit trail"
        estimate: 8
        priority: "critical"
      
      - type: "feature"
        title: "Notification service"
        description: "Email and push notification service with templates"
        estimate: 5
        priority: "medium"

quality_gates:
  - name: "API Response Time"
    type: "performance"
    threshold: "< 200ms (95th percentile)"
  - name: "Security Compliance"
    type: "security"
    threshold: "OWASP Top 10 passed"
  - name: "Documentation Coverage"
    type: "coverage"
    threshold: "100% API endpoints documented"

success_metrics:
  - metric: "API uptime"
    target: "> 99.9%"
  - metric: "Request rate"
    target: "> 1000 RPS"
  - metric: "Error rate"
    target: "< 0.1%"
```

## Task Pattern Templates

### Common Web Tasks

```yaml
# common-web-tasks.yaml
task_patterns:
  - name: "database_migration"
    type: "feature"
    template:
      title: "Database migration: {feature_name}"
      description: "Create and apply database migration for {feature_name}"
      estimate: 1
      priority: "medium"
      quality_criteria:
        - "Migration file created"
        - "Rollback script included"
        - "Test data provided"

  - name: "api_endpoint"
    type: "feature"
    template:
      title: "API endpoint: {endpoint_name}"
      description: "Implement {method} {endpoint} with {description}"
      estimate: 3
      priority: "medium"
      quality_criteria:
        - "OpenAPI documentation updated"
        - "Unit tests written"
        - "Error handling implemented"
        - "Input validation added"

  - name: "ui_component"
    type: "feature"
    template:
      title: "UI component: {component_name}"
      description: "Create {component_name} component with {functionality}"
      estimate: 2
      priority: "medium"
      quality_criteria:
        - "Component tested with Storybook"
        - "Responsive design implemented"
        - "Accessibility features added"
        - "Performance optimized"

  - name: "security_fix"
    type: "bug"
    template:
      title: "Security fix: {vulnerability}"
      description: "Fix {vulnerability} security issue in {component}"
      estimate: 2
      priority: "critical"
      quality_criteria:
        - "Security scan passed"
        - "Regression tests added"
        - "Documentation updated"

  - name: "performance_optimization"
    type: "tech_debt"
    template:
      title: "Performance: {optimization_target}"
      description: "Optimize {optimization_target} for better {metric}"
      estimate: 3
      priority: "medium"
      quality_criteria:
        - "Performance benchmarks improved"
        - "No functional regressions"
        - "Monitoring added"
```

### Quality Gates Templates

```yaml
# quality-gates.yaml
quality_gates:
  - name: "Test Coverage"
    type: "coverage"
    threshold: 80
    command: "pytest --cov=src --cov-report=xml"
    
  - name: "Security Scan"
    type: "security"
    threshold: "no_critical"
    command: "bandit -r src/ -f json"
    
  - name: "Code Quality"
    type: "quality"
    threshold: "no_issues"
    command: "ruff check src/ --format=json"
    
  - name: "Type Checking"
    type: "type_check"
    threshold: "no_errors"
    command: "mypy src/ --junit-xml reports/mypy.xml"
    
  - name: "Dependency Check"
    type: "dependencies"
    threshold: "no_vulnerabilities"
    command: "safety check --json"
    
  - name: "Performance Test"
    type: "performance"
    threshold: "response_time < 200ms"
    command: "pytest tests/performance/ --benchmark-only"
    
  - name: "Integration Test"
    type: "integration"
    threshold: "all_passed"
    command: "pytest tests/integration/ -v"
```

## CI/CD Integration Examples

### GitHub Actions Workflow

```yaml
# .github/workflows/planfile-auto-loop.yml
name: Planfile Auto-Loop

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM

jobs:
  auto-loop:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install planfile[all]
          pip install -r requirements.txt
      
      - name: Setup environment
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          echo "GITHUB_REPO=${{ github.repository }}" >> $GITHUB_ENV
      
      - name: Validate strategy
        run: planfile strategy validate --strategy .github/strategy.yaml
      
      - name: Run tests
        run: pytest tests/ -v --cov=src
      
      - name: Run auto-loop
        run: |
          planfile auto loop \
            --strategy .github/strategy.yaml \
            --project . \
            --backend github \
            --max-iterations 3 \
            --auto-fix \
            --output results.json
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: auto-loop-results
          path: results.json
      
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('results.json', 'utf8'));
            
            const comment = `## 🤖 Planfile Auto-Loop Results
            
            **Status**: ${results.success ? '✅ Success' : '❌ Failed'}
            **Iterations**: ${results.iterations}
            **Tickets Created**: ${results.tickets_created}
            **Bugs Fixed**: ${results.bugs_fixed}
            
            ${results.summary}
            `;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

### GitLab CI Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - test
  - analyze
  - fix
  - deploy

variables:
  PLANFILE_STRATEGY: ".gitlab/strategy.yaml"
  PLANFILE_BACKEND: "gitlab"

.test_template: &test_template
  image: python:3.11
  before_script:
    - pip install planfile[all]
    - pip install -r requirements.txt

unit_tests:
  <<: *test_template
  stage: test
  script:
    - pytest tests/unit/ -v --cov=src
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

security_scan:
  <<: *test_template
  stage: test
  script:
    - bandit -r src/ -f json -o security-report.json
  artifacts:
    reports:
      sast: security-report.json

planfile_analyze:
  <<: *test_template
  stage: analyze
  script:
    - planfile strategy validate --strategy $PLANFILE_STRATEGY
    - planfile backend test gitlab --permissions
  artifacts:
    reports:
      junit: planfile-report.xml

planfile_fix:
  <<: *test_template
  stage: fix
  script:
    - planfile auto loop \
        --strategy $PLANFILE_STRATEGY \
        --project . \
        --backend gitlab \
        --max-iterations 5 \
        --auto-fix \
        --output fix-results.json
  artifacts:
    reports:
      junit: fix-results.xml
  when: on_failure
  allow_failure: true

deploy_staging:
  stage: deploy
  script:
    - echo "Deploying to staging..."
  environment:
    name: staging
    url: https://staging.example.com
  only:
    - main
```

## Docker Examples

### Multi-stage Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Planfile
RUN pip install --no-cache-dir planfile[all]

# Development stage
FROM base as development
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["planfile", "auto", "loop", "--strategy", "strategy.yaml"]

# Production stage
FROM base as production
WORKDIR /app
COPY --from=development /app .
RUN pytest tests/ --cov=src
EXPOSE 8000
CMD ["planfile", "serve", "--port", "8000"]
```

### Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  planfile-runner:
    build: .
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_REPO=${GITHUB_REPO}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PLANFILE_LOG_LEVEL=INFO
    volumes:
      - .:/workspace
      - ./results:/app/results
      - ~/.planfile:/root/.planfile
    command: planfile auto loop --strategy strategy.yaml --max-iterations 10
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: planfile
      POSTGRES_USER: planfile
      POSTGRES_PASSWORD: planfile
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - planfile-runner

volumes:
  postgres_data:
  redis_data:
```

## Configuration Examples

### Environment-specific Strategies

```yaml
# strategy-dev.yaml
name: "Development Strategy"
project_type: "web"
environment: "development"

sprints:
  - id: 1
    name: "Feature Development"
    length_days: 7
    tasks:
      - type: "feature"
        title: "Implement new feature"
        estimate: 3
        auto_fix: true
    quality_gates:
      - name: "Unit Tests"
        threshold: 70
      - name: "Code Coverage"
        threshold: 70

---
# strategy-prod.yaml
name: "Production Strategy"
project_type: "web"
environment: "production"

sprints:
  - id: 1
    name: "Production Readiness"
    length_days: 14
    tasks:
      - type: "feature"
        title: "Production feature"
        estimate: 5
        auto_fix: false
    quality_gates:
      - name: "Unit Tests"
        threshold: 90
      - name: "Integration Tests"
        threshold: 100
      - name: "Security Scan"
        threshold: "no_critical"
      - name: "Performance Test"
        threshold: "response_time < 100ms"
```

### Multi-project Strategy

```yaml
# multi-project-strategy.yaml
name: "Multi-Project Coordination"
projects:
  - name: "frontend"
    path: "./frontend"
    strategy: "frontend-strategy.yaml"
    dependencies:
      - "backend-api"
  
  - name: "backend"
    path: "./backend"
    strategy: "backend-strategy.yaml"
    dependencies: []
  
  - name: "mobile"
    path: "./mobile"
    strategy: "mobile-strategy.yaml"
    dependencies:
      - "backend-api"

coordination:
  sync_points:
    - name: "API Contract Freeze"
      projects: ["frontend", "backend"]
      deadline: "2024-02-01"
    
    - name: "Integration Testing"
      projects: ["frontend", "backend", "mobile"]
      deadline: "2024-02-15"

shared_resources:
  - type: "design_system"
    location: "./shared/design-system"
    projects: ["frontend", "mobile"]
  
  - type: "api_specification"
    location: "./shared/api-spec"
    projects: ["frontend", "backend", "mobile"]
```

## Advanced Examples

### Custom Backend Integration

```python
# custom_backend.py
from strategy.integrations.base import BaseBackend
from strategy.models import Ticket

class CustomBackend(BaseBackend):
    def __init__(self, api_url: str, token: str):
        self.api_url = api_url
        self.token = token
    
    def create_issue(self, title: str, body: str, **kwargs) -> Ticket:
        # Custom implementation
        response = requests.post(
            f"{self.api_url}/issues",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"title": title, "body": body}
        )
        return Ticket.from_response(response.json())
    
    def update_issue(self, issue_id: str, **kwargs) -> Ticket:
        # Custom implementation
        pass
```

### Custom Quality Gates

```python
# custom_quality_gates.py
from strategy.ci_runner import QualityGate

class CustomQualityGate(QualityGate):
    def check(self, project_path: str) -> bool:
        # Custom quality check logic
        if self.name == "custom_performance":
            return self.check_performance(project_path)
        elif self.name == "custom_security":
            return self.check_security(project_path)
        return True
    
    def check_performance(self, project_path: str) -> bool:
        # Performance testing logic
        pass
    
    def check_security(self, project_path: str) -> bool:
        # Security scanning logic
        pass
```

---

**Planfile Examples** - Real-world templates and configurations for every use case. 🚀
