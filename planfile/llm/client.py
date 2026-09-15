"""LiteLLM client for plan generation.

Supports any LiteLLM-compatible model:
  - anthropic/claude-sonnet-4-20250514
  - openai/gpt-4o
  - ollama/qwen2.5-coder:7b
  - openrouter/deepseek/deepseek-chat-v3
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from planfile.llm.metrics import MetricsStore, elapsed_ms, new_correlation_id, store_from_config


def call_llm(
    prompt: str,
    model: str,
    temperature: float = 0.2,
    *,
    metrics_store: MetricsStore | str | Path | None = None,
    correlation_id: str | None = None,
) -> str:
    """Call LLM via LiteLLM. Falls back to llx proxy if available."""
    store = _coerce_store(metrics_store)
    correlation = correlation_id or new_correlation_id()
    attempt = 0

    def record(
        *,
        backend: str,
        started: float,
        started_at: str,
        status: str,
        response: object = None,
        error: BaseException | None = None,
    ) -> None:
        if store is None:
            return
        try:
            store.record_attempt(
                correlation_id=correlation,
                prompt=prompt,
                model=model,
                backend=backend,
                attempt=attempt,
                started_at=started_at,
                latency_ms=elapsed_ms(started),
                status=status,
                response=response,
                error=error,
            )
        except (OSError, TypeError, ValueError):
            # Observability must not change provider availability. The receipt
            # remains best-effort and any write failure is deliberately redacted.
            pass

    # Try 1: LiteLLM direct
    try:
        import litellm
    except ImportError:
        litellm = None
    if litellm is not None:
        attempt += 1
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        try:
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
            content = response.choices[0].message.content
        except Exception as exc:
            record(backend="litellm", started=started, started_at=started_at, status="failed", error=exc)
            raise
        record(backend="litellm", started=started, started_at=started_at, status="succeeded", response=response)
        return content

    # Try 2: llx proxy
    try:
        import httpx
        base_url = os.environ.get("LLX_LITELLM_URL", "http://localhost:4000")
        attempt += 1
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
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
        payload = resp.json()
        content = payload["choices"][0]["message"]["content"]
        record(backend="httpx-proxy", started=started, started_at=started_at, status="succeeded", response=payload)
        return content
    except Exception as exc:
        if attempt:
            record(backend="httpx-proxy", started=started, started_at=started_at, status="failed", error=exc)

    # Try 3: llx client
    try:
        from llx.config import LlxConfig
        from llx.routing.client import ChatMessage, LlxClient
        attempt += 1
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        with LlxClient(LlxConfig.load()) as client:
            response = client.chat([ChatMessage(role="user", content=prompt)], model=model)
            content = response.content
        record(backend="llx", started=started, started_at=started_at, status="succeeded", response=response)
        return content
    except ImportError as exc:
        if attempt:
            record(backend="llx", started=started, started_at=started_at, status="failed", error=exc)
        raise RuntimeError(
            "No LLM backend available. Install litellm (`pip install litellm`) "
            "or llx (`pip install llx`), or start LiteLLM proxy on localhost:4000."
        ) from exc
    except Exception as exc:
        record(backend="llx", started=started, started_at=started_at, status="failed", error=exc)
        raise


def _coerce_store(value: MetricsStore | str | Path | None) -> MetricsStore | None:
    if isinstance(value, MetricsStore):
        return value
    if value is not None:
        return MetricsStore(value)
    return store_from_config()
