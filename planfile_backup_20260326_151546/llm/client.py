"""LiteLLM client for plan generation.

Supports any LiteLLM-compatible model:
  - anthropic/claude-sonnet-4-20250514
  - openai/gpt-4o
  - ollama/qwen2.5-coder:7b
  - openrouter/deepseek/deepseek-chat-v3
"""

import os


def call_llm(prompt: str, model: str, temperature: float = 0.2) -> str:
    """Call LLM via LiteLLM. Falls back to llx proxy if available."""
    # Try 1: LiteLLM direct
    try:
        import litellm
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": "You are a software engineering planner. "
                 "Generate strategy YAML for code refactoring based on project metrics. "
                 "Output ONLY valid YAML wrapped in ```yaml``` blocks."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except ImportError:
        pass

    # Try 2: llx proxy
    try:
        import httpx
        base_url = os.environ.get("LLX_LITELLM_URL", "http://localhost:4000")
        resp = httpx.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 4096,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass

    # Try 3: llx client
    try:
        from llx.routing.client import LlxClient, ChatMessage
        from llx.config import LlxConfig
        with LlxClient(LlxConfig.load()) as client:
            response = client.chat([ChatMessage(role="user", content=prompt)], model=model)
            return response.content
    except ImportError:
        raise RuntimeError(
            "No LLM backend available. Install litellm (`pip install litellm`) "
            "or llx (`pip install llx`), or start LiteLLM proxy on localhost:4000."
        )
