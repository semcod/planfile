"""LiteLLM adapters for testing planfile with various LLM providers.

DEPRECATED: The canonical copy of this module now lives at
tests/llm_adapters.py.  This file is kept for backward compatibility
but may be removed in a future version.
"""

import warnings
from dataclasses import dataclass
from typing import Any

warnings.warn(
    "planfile.llm.adapters is deprecated — use tests/llm_adapters.py instead.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    import litellm
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False
    litellm = None

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None


@dataclass
class LLMTestResult:
    provider: str
    model: str
    success: bool
    response_time: float
    token_count: int | None = None
    cost: float | None = None
    error: str | None = None
    response: str | None = None


class BaseLLMAdapter:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__

    async def test_strategy_generation(self, strategy_prompt: str, model: str = None) -> LLMTestResult:
        raise NotImplementedError

    def get_available_models(self) -> list[str]:
        raise NotImplementedError


class LiteLLMAdapter(BaseLLMAdapter):
    pass


class OpenRouterAdapter(BaseLLMAdapter):
    pass


class LocalLLMAdapter(BaseLLMAdapter):
    pass


class LLMTestRunner:
    def __init__(self):
        self.adapters: dict[str, BaseLLMAdapter] = {}
        self.results: list[LLMTestResult] = []

    def register_adapter(self, name: str, adapter: BaseLLMAdapter):
        self.adapters[name] = adapter
