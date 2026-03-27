"""Generate strategy.yaml from code analysis + LLM.

Flow:
1. Collect metrics (code2llm .toon files or llx.analyze_project)
2. Build prompt with metrics + project structure
3. Send to LLM (via LiteLLM — any provider)
4. Parse YAML response → Strategy model
5. Validate against schema
"""

from pathlib import Path

import yaml

from planfile.llm.client import call_llm
from planfile.llm.prompts import build_strategy_prompt
from planfile.models import Strategy


def generate_strategy(
    project_path: str | Path,
    *,
    model: str | None = None,
    sprints: int = 3,
    focus: str | None = None,
    toon_dir: str | None = None,
    dry_run: bool = False,
) -> Strategy:
    """Generate a complete strategy from project analysis.

    Args:
        project_path: Project to analyze.
        model: LiteLLM model string (e.g. "anthropic/claude-sonnet-4-20250514").
                If None, uses llx to auto-select based on project metrics.
        sprints: Number of sprints to plan.
        focus: Focus area: "complexity", "duplication", "tests", "docs", or None (auto).
        toon_dir: Pre-existing .toon analysis files.
        dry_run: Show prompt but don't call LLM.
    """
    # 1. Collect metrics
    metrics = _collect_metrics(project_path, toon_dir)

    # 2. Build prompt
    prompt = build_strategy_prompt(metrics, sprints=sprints, focus=focus)

    if dry_run:
        print(prompt)
        return Strategy(sprints=[], quality_gates=[])

    # 3. Auto-select model if not specified
    if model is None:
        model = _auto_select_model(metrics)

    # 4. Call LLM
    response = call_llm(prompt, model=model)

    # 5. Parse + validate
    strategy = _parse_strategy_response(response)
    return strategy


def _collect_metrics(project_path: Path, toon_dir: str | None) -> dict:
    """Collect project metrics — try llx first, fallback to filesystem."""
    try:
        from llx import analyze_project
        metrics = analyze_project(str(project_path), toon_dir=toon_dir)
        return {
            "total_files": metrics.total_files,
            "total_lines": metrics.total_lines,
            "avg_cc": metrics.avg_cc,
            "max_cc": metrics.max_cc,
            "critical_count": metrics.critical_count,
            "god_modules": metrics.god_modules,
            "dup_groups": metrics.dup_groups,
            "languages": metrics.languages,
            "task_scope": metrics.task_scope,
        }
    except ImportError:
        # llx not installed — basic filesystem metrics
        return _basic_metrics(project_path)


def _auto_select_model(metrics: dict) -> str:
    """Use llx to select optimal model for plan generation."""
    try:
        from llx import analyze_project, select_model
        from llx.analysis.collector import ProjectMetrics
        pm = ProjectMetrics(**{k: v for k, v in metrics.items()
                               if hasattr(ProjectMetrics, k)})
        result = select_model(pm, task_hint="refactor")
        return result.model_id
    except ImportError:
        return "anthropic/claude-sonnet-4-20250514"  # sensible default


def _parse_strategy_response(response: str) -> Strategy:
    """Parse LLM YAML response into Strategy model."""
    # Extract YAML block from response
    yaml_text = response
    if "```yaml" in response:
        yaml_text = response.split("```yaml")[1].split("```")[0]
    elif "```" in response:
        yaml_text = response.split("```")[1].split("```")[0]

    # Fix common YAML formatting issues
    yaml_text = _fix_yaml_formatting(yaml_text)

    data = yaml.safe_load(yaml_text)
    return Strategy(**data)


def _fix_yaml_formatting(yaml_text: str) -> str:
    """Fix common YAML formatting issues from LLM responses."""
    lines = yaml_text.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        # Fix missing newlines after colons in list items
        if ': objectives:' in line and i > 0:
            # Check if this is a list item
            prev_line = lines[i-1].strip() if i > 0 else ''
            if prev_line.startswith('- '):
                # Insert newline before objectives
                fixed_lines.append('')  # Add empty line

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)


def _basic_metrics(project_path: Path) -> dict:
    """Fallback metrics from filesystem only."""
    import os
    files = lines = 0
    for root, dirs, fnames in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in fnames:
            if f.endswith(".py"):
                files += 1
                try:
                    lines += sum(1 for _ in open(Path(root) / f, "rb"))
                except OSError:
                    pass
    return {"total_files": files, "total_lines": lines, "avg_cc": 0, "max_cc": 0,
            "critical_count": 0, "god_modules": 0, "dup_groups": 0, "languages": ["py"]}
