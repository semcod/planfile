import time
from typing import Any

from ..base import BaseLLMAdapter
from ..constants import HAS_LITELLM, litellm, CONSTANT_4000
from ..models import LLMTestResult

class LiteLLMAdapter(BaseLLMAdapter):
    """Adapter for LiteLLM providers."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        if not HAS_LITELLM:
            raise ImportError("litellm is required. Install with: pip install litellm")

        # Configure LiteLLM
        if 'api_base' in config:
            litellm.api_base = config['api_base']
        if 'api_key' in config:
            litellm.api_key = config['api_key']

    async def test_strategy_generation(
        self,
        strategy_prompt: str,
        model: str = None
    ) -> LLMTestResult:
        """Test strategy generation using LiteLLM."""
        model = model or self.config.get('default_model', 'gpt-3.5-turbo')

        start_time = time.time()

        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a software engineering strategist. Generate comprehensive YAML strategies for software projects."
                    },
                    {
                        "role": "user",
                        "content": strategy_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=CONSTANT_4000
            )

            end_time = time.time()

            return LLMTestResult(
                provider="LiteLLM",
                model=model,
                success=True,
                response_time=end_time - start_time,
                token_count=response.usage.total_tokens if hasattr(response, 'usage') else None,
                cost=response._hidden_params.get('response_cost', None),
                response=response.choices[0].message.content
            )

        except Exception as e:
            end_time = time.time()
            return LLMTestResult(
                provider="LiteLLM",
                model=model,
                success=False,
                response_time=end_time - start_time,
                error=str(e)
            )

    def get_available_models(self) -> list[str]:
        """Get LiteLLM supported models."""
        return [
            # OpenAI
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            # Anthropic
            "anthropic/claude-3-opus-20240229",
            "anthropic/claude-3-sonnet-20240229",
            "anthropic/claude-3-haiku-20240307",
            # Google
            "gemini-pro",
            # Cohere
            "command-nightly",
            # Open source
            "replicate/llama-2-70b-chat",
            "togethercomputer/llama-2-70b-chat"
        ]