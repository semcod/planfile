"""Prompt templates for strategy generation."""


def build_strategy_prompt(
    metrics: dict,
    sprints: int = 3,
    focus: str | None = None,
) -> str:
    """Build a structured prompt for strategy generation."""
    focus_instruction = ""
    if focus == "complexity":
        focus_instruction = "Focus on reducing cyclomatic complexity: split god modules, extract functions."
    elif focus == "duplication":
        focus_instruction = "Focus on removing code duplication: extract shared functions, DRY patterns."
    elif focus == "tests":
        focus_instruction = "Focus on adding test coverage: unit tests, integration tests."
    elif focus == "docs":
        focus_instruction = "Focus on documentation: README, docstrings, examples."

    return f"""Analyze this project and generate a refactoring strategy in YAML format.

## Project Metrics
- Files: {metrics.get('total_files', '?')}
- Lines: {metrics.get('total_lines', '?')}
- Average Cyclomatic Complexity: {metrics.get('avg_cc', '?')}
- Max CC: {metrics.get('max_cc', '?')}
- Critical functions (CC≥15): {metrics.get('critical_count', '?')}
- God modules (>500L): {metrics.get('god_modules', '?')}
- Duplicate groups: {metrics.get('dup_groups', '?')}
- Languages: {', '.join(metrics.get('languages', ['unknown']))}

## Requirements
- Generate exactly {sprints} sprints
- Each sprint has 3-8 task patterns
- Each task has: name, task_type, description, priority, sprint_id, model_hints
- task_type: one of refactor, test, docs, feature, bugfix, security
- model_hints.planning: premium | balanced | cheap
- model_hints.implementation: balanced | cheap | local
- model_hints.review: premium | balanced
{focus_instruction}

## Output Format
```yaml
sprints:
  - id: sprint-1
    name: "Critical Fixes"
    goal: "Eliminate god modules and fix blocking issues"
    task_patterns:
      - name: "Split god module X"
        task_type: refactor
        description: "Split X.py (1082L, 7 classes) into sub-package"
        priority: critical
        model_hints:
          planning: premium
          implementation: balanced
          review: balanced
quality_gates:
  - name: "CC gate"
    metric: avg_cc
    threshold: 3.0
    operator: "<="

Generate the strategy YAML now:"""
