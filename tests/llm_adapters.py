"""
LiteLLM adapters for testing planfile with various LLM providers.
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    """Result of LLM test."""
    provider: str
    model: str
    success: bool
    response_time: float
    token_count: int | None = None
    cost: float | None = None
    error: str | None = None
    response: str | None = None


class BaseLLMAdapter:
    """Base class for LLM adapters."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__

    async def test_strategy_generation(
        self,
        strategy_prompt: str,
        model: str = None
    ) -> LLMTestResult:
        """Test strategy generation with the adapter."""
        raise NotImplementedError

    def get_available_models(self) -> list[str]:
        """Get list of available models."""
        raise NotImplementedError


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
                max_tokens=4000
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
            "max_tokens": 4000
        }

        start_time = time.time()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120.0
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

    async def _test_ollama(self, strategy_prompt: str, model: str) -> LLMTestResult:
        """Test with Ollama API."""
        payload = {
            "model": model,
            "prompt": f"You are a software engineering strategist. Generate comprehensive YAML strategies for software projects.\n\nUser: {strategy_prompt}\n\nAssistant:",
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 4000
            }
        }

        start_time = time.time()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=120.0
                )
                response.raise_for_status()

                data = response.json()
                end_time = time.time()

                return LLMTestResult(
                    provider="Ollama",
                    model=model,
                    success=True,
                    response_time=end_time - start_time,
                    response=data.get('response', '')
                )

        except Exception as e:
            end_time = time.time()
            return LLMTestResult(
                provider="Ollama",
                model=model,
                success=False,
                response_time=end_time - start_time,
                error=str(e)
            )

    async def _test_openai_compatible(self, strategy_prompt: str, model: str) -> LLMTestResult:
        """Test with OpenAI-compatible API."""
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
            "max_tokens": 4000
        }

        start_time = time.time()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=120.0
                )
                response.raise_for_status()

                data = response.json()
                end_time = time.time()

                return LLMTestResult(
                    provider="Local",
                    model=model,
                    success=True,
                    response_time=end_time - start_time,
                    token_count=data.get('usage', {}).get('total_tokens'),
                    response=data['choices'][0]['message']['content']
                )

        except Exception as e:
            end_time = time.time()
            return LLMTestResult(
                provider="Local",
                model=model,
                success=False,
                response_time=end_time - start_time,
                error=str(e)
            )

    def get_available_models(self) -> list[str]:
        """Get local models."""
        if self.provider == 'ollama':
            return ['llama2', 'codellama', 'mistral', 'vicuna']
        return ['local-model']


class LLMTestRunner:
    """Run tests across multiple LLM adapters."""

    def __init__(self):
        self.adapters: dict[str, BaseLLMAdapter] = {}
        self.results: list[LLMTestResult] = []

    def register_adapter(self, name: str, adapter: BaseLLMAdapter):
        """Register an LLM adapter."""
        self.adapters[name] = adapter

    async def test_strategy_with_all_adapters(
        self,
        strategy_file: Path,
        models_per_adapter: dict[str, list[str]] = None
    ) -> dict[str, list[LLMTestResult]]:
        """Test a strategy with all registered adapters."""
        # Read strategy file
        with open(strategy_file) as f:
            strategy_content = f.read()

        # Create test prompt
        prompt = f"""
        Generate a comprehensive software development strategy based on this template:
        
        {strategy_content}
        
        Please create a new strategy for a different project type while maintaining the same structure and quality.
        """

        results = {}

        for adapter_name, adapter in self.adapters.items():
            print(f"\n🔄 Testing with {adapter_name}...")
            adapter_results = []

            models = models_per_adapter.get(adapter_name, [None])

            for model in models:
                result = await adapter.test_strategy_generation(prompt, model)
                adapter_results.append(result)

                status = "✅" if result.success else "❌"
                print(f"  {status} {model or 'default'}: {result.response_time:.2f}s")

                if result.error:
                    print(f"    Error: {result.error}")

            results[adapter_name] = adapter_results

        return results

    def generate_report(self, results: dict[str, list[LLMTestResult]]) -> str:
        """Generate a test report."""
        report_sections = [
            self._generate_header(),
            self._generate_summary_table(results),
            self._generate_detailed_results(results),
        ]
        return "\n".join(report_sections)

    def _generate_header(self) -> str:
        """Generate report header."""
        return "# LLM Adapter Test Report\n"

    def _generate_summary_table(self, results: dict[str, list[LLMTestResult]]) -> str:
        """Generate summary table section."""
        report = ["## Summary\n"]
        report.append("| Adapter | Model | Success | Time (s) | Tokens | Cost |")
        report.append("|---------|-------|---------|----------|--------|------|")

        for adapter_name, adapter_results in results.items():
            for result in adapter_results:
                report.append(
                    f"| {result.provider} | {result.model or 'default'} | "
                    f"{'✅' if result.success else '❌'} | {result.response_time:.2f} | "
                    f"{result.token_count or '-'} | ${result.cost or '-'} |"
                )

        return "\n".join(report)

    def _generate_detailed_results(self, results: dict[str, list[LLMTestResult]]) -> str:
        """Generate detailed results section."""
        report = ["\n## Detailed Results\n"]

        for adapter_name, adapter_results in results.items():
            report.append(f"### {adapter_name}\n")

            successful = [r for r in adapter_results if r.success]
            failed = [r for r in adapter_results if not r.success]

            if successful:
                report.append(self._generate_successful_tests_section(successful))

            if failed:
                report.append(self._generate_failed_tests_section(failed))

        return "\n".join(report)

    def _generate_successful_tests_section(self, successful: list[LLMTestResult]) -> str:
        """Generate successful tests section."""
        section = ["#### Successful Tests\n"]
        for result in successful:
            section.append(f"**Model:** {result.model or 'default'}\n")
            section.append(f"- Response time: {result.response_time:.2f}s\n")
            if result.token_count:
                section.append(f"- Tokens: {result.token_count}\n")
            if result.cost:
                section.append(f"- Cost: ${result.cost:.4f}\n")
            section.append(f"- Response preview: {result.response[:200]}...\n")
        return "\n".join(section)

    def _generate_failed_tests_section(self, failed: list[LLMTestResult]) -> str:
        """Generate failed tests section."""
        section = ["#### Failed Tests\n"]
        for result in failed:
            section.append(f"**Model:** {result.model or 'default'}\n")
            section.append(f"- Error: {result.error}\n")
        return "\n".join(section)
