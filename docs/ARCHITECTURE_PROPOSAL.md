# Planfile Architecture Proposal: Clear Sources of Truth

## Problem Statement
Currently planfile has confusing data storage:
- `planfile.yaml` contains strategy metadata with unused `tickets: {}` fields
- `.planfile/sprints/` contains the actual tickets (runtime data)
- Integration configurations are mixed with ticket data
- Users are confused about where the "real" data lives

## Proposed Architecture

### 1. Single Source of Truth for Tasks: `.planfile/`
The `.planfile/` directory becomes the canonical store for ALL ticket data:

```
.planfile/
├── config.yaml          # Project configuration (name, prefix, etc.)
├── sprints/
│   ├── current.yaml     # Current sprint tickets
│   ├── backlog.yaml     # Backlog tickets
│   └── done.yaml        # Completed tickets
└── sync/
    └── [integration-sync-state]
```

### 2. Single Source of Truth for Integrations: `integrations.yaml`
All integration configurations move to a dedicated file:

```yaml
# integrations.yaml
integrations:
  github:
    type: github
    config:
      token: ${GITHUB_TOKEN}
      repo: semcod/planfile
    sync:
      enabled: true
      direction: both
      
  gitlab:
    type: gitlab
    config:
      token: ${GITLAB_TOKEN}
      project_id: ${GITLAB_PROJECT_ID}
    sync:
      enabled: true
      direction: both
      
  jira:
    type: jira
    config:
      email: ${JIRA_EMAIL}
      token: ${JIRA_TOKEN}
      url: ${JIRA_URL}
      project: ${JIRA_PROJECT}
    sync:
      enabled: true
      direction: both
```

### 3. Simplified `planfile.yaml`
The main planfile.yaml becomes purely strategic:

```yaml
# planfile.yaml
name: "Project Strategy"
description: "High-level project strategy and goals"

project:
  name: "My Project"
  description: "Project description"
  prefix: "PROJ"

strategy:
  goals:
    - "Goal 1"
    - "Goal 2"
  
  quality_gates:
    - "CC̄ ≤ 3.0"
    - "Test coverage ≥ 80%"
```

## Migration Plan

### Phase 1: Update Core Models
1. Remove `tickets: {}` from Sprint model in planfile.yaml
2. Ensure all ticket operations use `.planfile/sprints/` exclusively

### Phase 2: Create Integration Config Module
1. Create `planfile/core/integrations.py` for integration config management
2. Update importers to use integration configs from `integrations.yaml`
3. Add `planfile integrations` CLI command for managing integrations

### Phase 3: Update Examples
1. Split all examples into:
   - `planfile.yaml` (strategy only)
   - `integrations.yaml` (integration configs)
   - Ticket data in `.planfile/` (runtime)
2. Update documentation to reflect clear separation

### Phase 4: CLI Updates
1. `planfile ticket` commands always work with `.planfile/`
2. `planfile sync` uses `integrations.yaml`
3. `planfile import` uses integration configs for tool-specific settings

## Benefits

1. **Clarity**: Everyone knows where to find what
   - Tasks → `.planfile/`
   - Integrations → `integrations.yaml`
   - Strategy → `planfile.yaml`

2. **Separation of Concerns**:
   - Runtime data (tickets) separate from configuration
   - Integration configs separate from project strategy
   - Each file has a single responsibility

3. **Better UX**:
   - No more confusion about why `planfile.yaml` doesn't show tickets
   - Clear mental model for users
   - Easier to backup/sync specific parts

## Implementation Tasks

- [ ] Update Sprint model to remove tickets field
- [ ] Create IntegrationConfig model and manager
- [ ] Add integrations.yaml support
- [ ] Update all importers to use integration configs
- [ ] Create `planfile integrations` CLI command
- [ ] Update all examples to use new structure
- [ ] Update documentation
- [ ] Add migration guide for existing users
