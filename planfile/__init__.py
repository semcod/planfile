"""Planfile - Strategic project planning and execution.

This package provides:
- Strategy and sprint modeling in YAML
- Task execution with intelligent model selection
- Integration with various LLM providers
- CLI and API for applying and reviewing strategies
"""

__version__ = "0.1.20"
__author__ = "Tom Sapletta"
__email__ = "tom@sapletta.com"

# Core models
from .models import Strategy as StrategyV1, Sprint, TaskPattern, TaskType, ModelHints, ModelTier

# V2 - Simplified models (recommended for new code)
from .models_v2 import Strategy as StrategyV2, Task, Goal, QualityGate, ModelTier as ModelTierV2

# Executors
from .runner import load_valid_strategy, run_strategy, verify_strategy_post_execution
from .executor_standalone import StrategyExecutor, execute_strategy, TaskResult, LLMClient
from .executor_standalone import create_openai_client, create_litellm_client

# Export both versions for backward compatibility
__all__ = [
    # V1 - Original (for backward compatibility)
    "StrategyV1",
    "Sprint", 
    "TaskPattern",
    "TaskType",
    "ModelHints",
    "ModelTier",
    
    # V2 - Simplified (recommended)
    "StrategyV2",
    "Task",
    "Goal", 
    "QualityGate",
    "ModelTierV2",
    "StrategyExecutor",
    "execute_strategy",
    "TaskResult",
    "LLMClient",
    "create_openai_client",
    "create_litellm_client",
    
    # Common
    "load_valid_strategy",
    "run_strategy",
    "verify_strategy_post_execution",
]

# Default to V2 for new code
Strategy = StrategyV2
