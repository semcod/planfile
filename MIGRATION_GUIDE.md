# Planfile V2 Migration Guide

## Overview
Planfile V2 introduces a simplified, more robust format based on real-world testing experience. This guide helps you migrate from V1 to V2.

## Key Improvements

### 1. **Simplified Task Structure**
Tasks are now embedded directly in sprints instead of being defined separately.

**V1 (Complex):**
```yaml
sprints:
  - id: 1
    name: "Sprint 1"
    tasks: ["task1", "task2"]  # References to task patterns

tasks:
  patterns:
    - id: "task1"
      name: "Actual Task Name"
      type: "feature"
      description: "..."
```

**V2 (Simple):**
```yaml
sprints:
  - id: 1
    name: "Sprint 1"
    tasks:  # Tasks defined directly
      - name: "Actual Task Name"
        type: "feature"
        description: "..."
```

### 2. **Flexible Model Hints**
Model hints now accept simple strings.

**V1:**
```yaml
model_hints:
  implementation: "balanced"
```

**V2 (both work):**
```yaml
model_hints: "balanced"  # Simple string
# OR
model_hints:
  implementation: "balanced"
```

### 3. **Relaxed Validation**
- Added common task types: `refactor`, `test`
- Added `free` as alias for `cheap` model tier
- Criteria can be string or list
- More fields have sensible defaults

### 4. **Error Tolerance**
The V2 loader handles various formats gracefully:
- Missing optional fields get defaults
- String criteria auto-convert to lists
- Mixed task formats are accepted

## Migration Steps

### Step 1: Update Your Strategy Files

1. **Move tasks into sprints:**
   ```yaml
   # Before
   sprints:
     - id: 1
       tasks: ["refactor-method"]
   
   tasks:
     patterns:
       - id: "refactor-method"
         name: "Extract Method"
         # ...
   
   # After
   sprints:
     - id: 1
       tasks:
         - name: "Extract Method"
           # ...
   ```

2. **Simplify model hints (optional):**
   ```yaml
   # Before
   model_hints:
     implementation: "cheap"
   
   # After
   model_hints: "cheap"
   ```

3. **Use new task types (optional):**
   ```yaml
   # Instead of tech_debt for refactoring
   type: "refactor"
   
   # For testing tasks
   type: "test"
   ```

### Step 2: Update Your Code

**Loading strategies:**
```python
# V1
from planfile import Strategy
strategy = Strategy(**data)

# V2 (more flexible)
from planfile import Strategy
strategy = Strategy.load_flexible(data)  # Accepts dict, file path, etc.
```

**Executing strategies:**
```python
# V1 - complex
from planfile.runner import StrategyRunner
runner = StrategyRunner(backends)
results = runner.apply_strategy(strategy, path)

# V2 - simple
from planfile import execute_strategy
results = execute_strategy("strategy.yaml", path, dry_run=True)
```

### Step 3: Test Your Changes

Use the built-in test script:
```bash
python3 test_improvements.py
```

## Backward Compatibility

V2 maintains backward compatibility:
- V1 models are available as `StrategyV1`, `TaskPattern`, etc.
- V2 can load and convert V1 formats automatically
- Existing code continues to work

## Common Migration Patterns

### Pattern 1: Simple Refactoring Strategy

```yaml
name: "Code Cleanup"
goal: "Reduce technical debt"

sprints:
  - id: 1
    name: "Refactoring"
    objectives: ["Extract methods", "Add tests"]
    tasks:
      - name: "Extract Complex Methods"
        description: "Methods with CC > 10"
        type: "refactor"
        model_hints: "balanced"
      
      - name: "Add Unit Tests"
        description: "Test extracted methods"
        type: "test"
        model_hints: "free"
```

### Pattern 2: Feature Development

```yaml
name: "New Feature"
goal: "Implement user authentication"

sprints:
  - id: 1
    name: "Backend"
    tasks:
      - name: "Design Auth API"
        type: "feature"
        model_hints: "premium"
      
      - name: "Implement Auth Service"
        type: "feature"
        model_hints: "balanced"
  
  - id: 2
    name: "Frontend"
    tasks:
      - name: "Create Login UI"
        type: "feature"
        model_hints: "balanced"
      
      - name: "Add Tests"
        type: "test"
        model_hints: "cheap"
```

## Troubleshooting

### Error: "task_patterns not found"
**Solution:** Tasks are now embedded in sprints. Move them there.

### Error: "Invalid TaskType"
**Solution:** Use valid types: `feature`, `tech_debt`, `bug`, `chore`, `documentation`, `refactor`, `test`

### Error: "Invalid ModelTier"
**Solution:** Use valid tiers: `local`, `cheap`, `balanced`, `premium` (or `free` as alias)

## Best Practices

1. **Start Simple:** Use the V2 format for new strategies
2. **Migrate Gradually:** Convert V1 strategies when convenient
3. **Use Dry Run:** Always test with `dry_run=True` first
4. **Model Hints:** Use `cheap`/`free` for simple tasks, `balanced` for complex, `premium` for critical
5. **Task Types:** Use specific types (`refactor`, `test`) for better organization

## Example: Complete V2 Strategy

See `examples/strategy_simple_v2.yaml` for a complete example of the V2 format.
