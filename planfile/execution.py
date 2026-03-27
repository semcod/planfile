"""Execution bridge — thin wrapper over executor_standalone.

New code should import from here. The heavy logic stays in
executor_standalone.py until it is fully refactored.
"""

from planfile.executor_standalone import (
    LLMClient,
    StrategyExecutor,
    TaskResult,
    create_litellm_client,
    create_openai_client,
    execute_strategy,
)

__all__ = [
    "StrategyExecutor",
    "LLMClient",
    "TaskResult",
    "execute_strategy",
    "create_openai_client",
    "create_litellm_client",
]
