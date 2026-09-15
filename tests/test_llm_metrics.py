"""Offline contract tests for redacted LLM metrics and receipts."""

import json
import sys
import types

from planfile.llm.client import call_llm
from planfile.llm.metrics import EXPORT_SCHEMA, METRICS_SCHEMA, MetricsStore


class _Usage:
    prompt_tokens = 7
    completion_tokens = 5
    total_tokens = 12


class _Message:
    content = "safe response"


class _Choice:
    message = _Message()


class _Response:
    choices = [_Choice()]
    usage = _Usage()
    response_cost = 0.0125


def test_success_receipt_is_redacted_and_contains_usage(tmp_path):
    store = MetricsStore(tmp_path / "llm.jsonl")
    record = store.record_attempt(
        correlation_id="corr-1",
        prompt="credential=do-not-store",
        model="test/model",
        backend="litellm",
        attempt=1,
        started_at="2026-09-15T00:00:00+00:00",
        latency_ms=12.3456,
        status="succeeded",
        response=_Response(),
    )

    assert record["schema"] == METRICS_SCHEMA
    assert record["input_tokens"] == 7
    assert record["output_tokens"] == 5
    assert record["total_tokens"] == 12
    assert record["cost_usd"] == 0.0125
    raw = (tmp_path / "llm.jsonl").read_text(encoding="utf-8")
    assert "credential=do-not-store" not in raw
    assert "safe response" not in raw


def test_missing_usage_and_cost_remain_unknown(tmp_path):
    store = MetricsStore(tmp_path / "llm.jsonl")
    record = store.record_attempt(
        correlation_id="corr-2",
        prompt="prompt",
        model="test/model",
        backend="proxy",
        attempt=1,
        started_at="2026-09-15T00:00:00+00:00",
        latency_ms=1,
        status="succeeded",
        response={"choices": [{"message": {"content": "ok"}}]},
    )
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["total_tokens"] is None
    assert record["cost_usd"] is None


def test_failed_attempt_keeps_error_type_only(tmp_path):
    store = MetricsStore(tmp_path / "llm.jsonl")
    record = store.record_attempt(
        correlation_id="corr-3",
        prompt="secret prompt",
        model="test/model",
        backend="proxy",
        attempt=2,
        started_at="2026-09-15T00:00:00+00:00",
        latency_ms=2,
        status="failed",
        error=RuntimeError("token=private"),
    )
    assert record["error_type"] == "RuntimeError"
    assert record["retry_count"] == 1
    raw = (tmp_path / "llm.jsonl").read_text(encoding="utf-8")
    assert "token=private" not in raw
    assert "secret prompt" not in raw


def test_client_records_direct_provider_call(tmp_path, monkeypatch):
    fake = types.SimpleNamespace(completion=lambda **_: _Response())
    monkeypatch.setitem(sys.modules, "litellm", fake)
    store = MetricsStore(tmp_path / "llm.jsonl")

    assert call_llm("prompt", "test/model", metrics_store=store, correlation_id="corr-direct") == "safe response"
    records = store.load()
    assert len(records) == 1
    assert records[0]["backend"] == "litellm"
    assert records[0]["correlation_id"] == "corr-direct"


def test_client_records_proxy_fallback(tmp_path, monkeypatch):
    class _HTTPResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "proxy response"}}]}

    fake_httpx = types.SimpleNamespace(post=lambda *_args, **_kwargs: _HTTPResponse())
    monkeypatch.setitem(sys.modules, "litellm", None)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    store = MetricsStore(tmp_path / "llm.jsonl")

    assert call_llm("prompt", "test/model", metrics_store=store) == "proxy response"
    records = store.load()
    assert len(records) == 1
    assert records[0]["backend"] == "httpx-proxy"


def test_export_is_digest_bound_and_deterministic(tmp_path):
    store = MetricsStore(tmp_path / "llm.jsonl")
    for attempt, latency in ((1, 10), (2, 20)):
        store.record_attempt(
            correlation_id=f"corr-{attempt}", prompt="same", model="m", backend="b",
            attempt=attempt, started_at="now", latency_ms=latency,
            status="succeeded" if attempt == 2 else "failed",
            response=_Response() if attempt == 2 else None,
            error=ValueError("hidden") if attempt == 1 else None,
        )
    first = store.export()
    second = store.export()
    assert first == second
    assert first["schema"] == EXPORT_SCHEMA
    assert first["calls"] == 2
    assert first["fallbacks"] == 1
    assert first["cost_usd"] == 0.0125
    assert json.dumps(first, sort_keys=True)
