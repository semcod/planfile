from typing import Any

from ..base import BaseLLMAdapter
from ..constants import HAS_HTTPX
from ..models import LLMTestResult

class LocalLLMAdapter(BaseLLMAdapter):
    """Adapter for local LLM servers (Ollama, LM Studio, etc.)."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.provider = config.get('provider', 'ollama')

    async def test_strategy_generation(
        self,
        strategy_prompt: str,
        model: str = None
    ) -> LLMTestResult:
        """Test strategy generation using local LLM."""
        if not HAS_HTTPX:
            raise ImportError("httpx is required. Install with: pip install httpx")

        model = model or self.config.get('default_model', 'llama2')

        if self.provider == 'ollama':
            return await self._test_ollama(strategy_prompt, model)
        else:
            return await self._test_openai_compatible(strategy_prompt, model)

    def get_available_models(self) -> list[str]:
        """Get available models for local LLM."""
        # Placeholder - in a real implementation, this might query the server
        return ["llama2", "codellama"]