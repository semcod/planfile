"""
Strategy package - Strategic PM layer for ticket systems.

This package provides:
- Strategy and sprint modeling in YAML
- Integration with external ticket systems (Jira, GitHub, GitLab)
- CLI and API for applying and reviewing strategies
"""

__version__ = "0.1.16"
__author__ = "Tom Sapletta"
__email__ = "tom@sapletta.com"

# Original models
from .models import Strategy as StrategyV1, Sprint, TaskPattern, TaskType, ModelHints, ModelTier

# New simplified models
from .models_v2 import Strategy as StrategyV2, Task, Goal, QualityGate, ModelTier as ModelTierV2

# Executor
from .executor_v2 import StrategyExecutor, execute_strategy, TaskResult

# Export both versions for backward compatibility
__all__ = [
    # V1 - Original
    "StrategyV1",
    "Sprint", 
    "TaskPattern",
    "TaskType",
    "ModelHints",
    "ModelTier",
    
    # V2 - Simplified
    "StrategyV2",
    "Task",
    "Goal", 
    "QualityGate",
    "ModelTierV2",
    "StrategyExecutor",
    "execute_strategy",
    "TaskResult",
]

# Default to V2 for new code
Strategy = StrategyV2
