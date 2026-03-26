"""Simplified strategy executor that works with the new model format."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import logging

from .models_v2 import Strategy, Task, ModelTier

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of executing a task."""
    task_name: str
    status: str  # "success", "failed", "skipped", "dry_run"
    model_used: str
    response: str = ""
    error: Optional[str] = None
    execution_time: Optional[float] = None


class StrategyExecutor:
    """Simplified strategy executor."""
    
    def __init__(self, llx_client=None, config=None):
        """Initialize executor.
        
        Args:
            llx_client: LLX client for LLM calls (optional)
            config: Configuration dictionary or LlxConfig (optional)
        """
        self.client = llx_client
        # Handle both dict and LlxConfig
        if config and hasattr(config, 'models'):
            # It's an LlxConfig object
            self.config = {
                'model_map': {
                    'local': config.models.get('local', {}).model_id if config.models.get('local') else 'ollama/qwen2.5-coder:7b',
                    'cheap': config.models.get('cheap', {}).model_id if config.models.get('cheap') else 'openrouter/meta-llama/llama-3.2-3b-instruct:free',
                    'balanced': config.models.get('balanced', {}).model_id if config.models.get('balanced') else 'openai/gpt-4o-mini',
                    'premium': config.models.get('premium', {}).model_id if config.models.get('premium') else 'openai/gpt-4o',
                    'free': config.models.get('free', {}).model_id if config.models.get('free') else 'openrouter/meta-llama/llama-3.2-3b-instruct:free'
                }
            }
        else:
            # It's a dict or None
            self.config = config or {}
    
    def execute_strategy(
        self,
        strategy: Union[Strategy, str, Path, Dict],
        project_path: Union[str, Path] = ".",
        *,
        dry_run: bool = False,
        sprint_filter: Optional[int] = None,
        model_override: Optional[str] = None,
        on_progress: Optional[callable] = None
    ) -> List[TaskResult]:
        """Execute a strategy.
        
        Args:
            strategy: Strategy object or path to YAML file
            project_path: Path to the project
            dry_run: If True, only simulate execution
            sprint_filter: Execute only this sprint (optional)
            model_override: Override model selection
            on_progress: Progress callback function
            
        Returns:
            List of task results
        """
        # Load strategy if needed
        if not isinstance(strategy, Strategy):
            strategy = Strategy.load_flexible(strategy)
        
        results = []
        
        # Process sprints
        for sprint in strategy.sprints:
            if sprint_filter and sprint.id != sprint_filter:
                continue
            
            if on_progress:
                on_progress(f"Sprint {sprint.id}: {sprint.name}")
            
            # Process tasks
            for task in sprint.tasks:
                if on_progress:
                    on_progress(f"  Task: {task.name}")
                
                result = self._execute_task(
                    task, 
                    project_path, 
                    dry_run, 
                    model_override
                )
                results.append(result)
        
        return results
    
    def _execute_task(
        self,
        task: Task,
        project_path: Union[str, Path],
        dry_run: bool,
        model_override: Optional[str] = None
    ) -> TaskResult:
        """Execute a single task."""
        import time
        start_time = time.time()
        model = None
        
        try:
            # Select model
            model = model_override or self._select_model(task)
            
            if dry_run:
                return TaskResult(
                    task_name=task.name,
                    status="dry_run",
                    model_used=model,
                    execution_time=time.time() - start_time
                )
            
            # Build prompt
            prompt = self._build_prompt(task, project_path)
            
            # Execute if client available
            if self.client:
                response = self.client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=model
                )
                content = response.content if hasattr(response, 'content') else str(response)
            else:
                # Mock execution for testing
                content = f"Mock execution of task '{task.name}' with model {model}"
            
            return TaskResult(
                task_name=task.name,
                status="success",
                model_used=model,
                response=content,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return TaskResult(
                task_name=task.name,
                status="failed",
                model_used=model or "unknown",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _select_model(self, task: Task) -> str:
        """Select model based on task hints and type."""
        # Get model hint from task
        hints = task.model_hints or {}
        hint = hints.get('implementation') or hints.get('design', 'balanced')
        
        # Map hint to actual model
        model_map = self.config.get('model_map', {
            'local': 'ollama/qwen2.5-coder:7b',
            'cheap': 'openrouter/meta-llama/llama-3.2-3b-instruct:free',
            'balanced': 'openai/gpt-4o-mini',
            'premium': 'openai/gpt-4o',
            'free': 'openrouter/meta-llama/llama-3.2-3b-instruct:free'
        })
        
        # Select model based on task type if no hint
        if not hints:
            if task.type in ['chore', 'documentation']:
                hint = 'cheap'
            elif task.type in ['tech_debt', 'refactor']:
                hint = 'balanced'
            else:
                hint = 'balanced'
        
        return model_map.get(hint, model_map['balanced'])
    
    def _build_prompt(self, task: Task, project_path: Union[str, Path]) -> str:
        """Build execution prompt for task."""
        # Try to get project metrics if available
        metrics = self._get_project_metrics(project_path)
        
        prompt = f"""## Task: {task.name}

Type: {task.type}
Priority: {task.priority}

Description:
{task.description}

"""
        
        if metrics:
            prompt += f"""
## Project Context
- Files: {metrics.get('total_files', 'N/A')}
- Lines of code: {metrics.get('total_lines', 'N/A')}
- Average complexity: {metrics.get('avg_cc', 'N/A')}
- Max complexity: {metrics.get('max_cc', 'N/A')}

"""
        
        prompt += """
## Instructions
Please execute this task. Provide:
1. Specific actions to take
2. Code changes if applicable (with file paths)
3. Any additional context or notes

Focus on practical, actionable steps.
"""
        
        return prompt
    
    def _get_project_metrics(self, project_path: Union[str, Path]) -> Optional[Dict]:
        """Get project metrics if available."""
        try:
            # Try to import LLX metrics collector
            from llx.analysis.collector import ProjectMetrics
            
            metrics = ProjectMetrics.collect(str(project_path))
            return {
                'total_files': metrics.total_files,
                'total_lines': metrics.total_lines,
                'avg_cc': metrics.avg_cc,
                'max_cc': metrics.max_cc
            }
        except Exception:
            # Fallback to simple metrics
            try:
                path = Path(project_path)
                py_files = list(path.rglob("*.py"))
                return {
                    'total_files': len(py_files),
                    'total_lines': sum(len(f.read_text().splitlines()) for f in py_files if f.is_file()),
                    'avg_cc': 'N/A',
                    'max_cc': 'N/A'
                }
            except Exception:
                return None


# Convenience function for backward compatibility
def execute_strategy(
    strategy_path: Union[str, Path],
    project_path: Union[str, Path] = ".",
    *,
    dry_run: bool = False,
    sprint_filter: Optional[int] = None,
    **kwargs
) -> List[TaskResult]:
    """Execute strategy from file - convenience function."""
    executor = StrategyExecutor()
    return executor.execute_strategy(
        strategy=strategy_path,
        project_path=project_path,
        dry_run=dry_run,
        sprint_filter=sprint_filter,
        **kwargs
    )
