from typing import Any

class BaseLLMAdapter:
    """Base class for LLM adapters."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__

    async def test_strategy_generation(
        self,
        strategy_prompt: str,
        model: str = None
    ) -> 'LLMTestResult':
        """Test strategy generation with the adapter."""
        raise NotImplementedError

    def get_available_models(self) -> list[str]:
        """Get list of available models."""
        raise NotImplementedError