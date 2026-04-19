import os
import time
from typing import Any

from ..base import BaseLLMAdapter
from ..constants import HAS_HTTPX, httpx, CONSTANT_120, CONSTANT_4000
from ..models import LLMTestResult

class OpenRouterAdapter(BaseLLMAdapter):
    """Adapter for OpenRouter API."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key') or os.environ.get('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1"

        if not self.api_key:
            raise ValueError("OpenRouter API key required. Set OPENROUTER_API_KEY or pass in config")

    async def test_strategy_generation(
        self,
        strategy_prompt: str,
        model: str = None
    ) -> LLMTestResult:
        """Test strategy generation using OpenRouter."""
        if not HAS_HTTPX:
            raise ImportError("httpx is required. Install with: pip install httpx")

        model = model or self.config.get('default_model', 'anthropic/claude-3-haiku')

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/wronai/planfile",
            "X-Title": "Planfile Strategy Generation"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a software engineering strategist. Generate comprehensive YAML strategies for software projects."
                },
                {
                    "role": "user",
                    "content": strategy_prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": CONSTANT_4000
        }

        start_time = time.time()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=CONSTANT_120
                )
                response.raise_for_status()

                data = response.json()
                end_time = time.time()

                return LLMTestResult(
                    provider="OpenRouter",
                    model=model,
                    success=True,
                    response_time=end_time - start_time,
                    token_count=data.get('usage', {}).get('total_tokens'),
                    response=data['choices'][0]['message']['content']
                )

        except Exception as e:
            end_time = time.time()
            return LLMTestResult(
                provider="OpenRouter",
                model=model,
                success=False,
                response_time=end_time - start_time,
                error=str(e)
            )

    def get_available_models(self) -> list[str]:
        """Get OpenRouter available models."""
        return [
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "anthropic/claude-3-haiku",
            "openai/gpt-4",
            "openai/gpt-4-turbo",
            "openai/gpt-3.5-turbo",
            "google/gemini-pro",
            "meta-llama/llama-3-70b-instruct",
            "mistralai/mixtral-8x7b-instruct"
        ]