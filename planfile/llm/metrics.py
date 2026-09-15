"""Redacted, replayable observations for LLM calls.

The metrics file is evidence, not a transcript.  Request and response content
are represented by SHA-256 digests, while provider usage/cost fields remain
nullable when a backend does not return them.  A receipt can therefore be
replayed or joined to another system by digest without granting access to the
prompt, response, or credentials.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

from planfile.core.fastio import _atomic_write_text

METRICS_SCHEMA = "planfile.llm-metrics/v1"
EXPORT_SCHEMA = "planfile.llm-metrics-export/v1"
DEFAULT_METRICS_PATH = ".planfile/metrics/llm.jsonl"


def _safe_text(value: object, limit: int = 128) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\x00", " ")
    return text[:limit] or None


def _digest(value: object) -> str:
    if isinstance(value, bytes):
        raw = value
    else:
        raw = str(value).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _finite_number(value: object, *, integer: bool = False) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    if integer:
        return int(number)
    return number


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _usage(response: object) -> tuple[int | None, int | None, int | None]:
    usage = _field(response, "usage")
    if usage is None:
        return None, None, None
    input_tokens = _finite_number(
        _field(usage, "prompt_tokens", _field(usage, "input_tokens")), integer=True
    )
    output_tokens = _finite_number(
        _field(usage, "completion_tokens", _field(usage, "output_tokens")), integer=True
    )
    total_tokens = _finite_number(_field(usage, "total_tokens"), integer=True)
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def _response_cost(response: object) -> float | None:
    candidates = [_field(response, "response_cost"), _field(response, "cost")]
    hidden = _field(response, "_hidden_params")
    if hidden is not None:
        candidates.append(_field(hidden, "response_cost"))
    for candidate in candidates:
        cost = _finite_number(candidate)
        if cost is not None:
            return cost
    return None


def _response_content(response: object) -> str:
    choices = _field(response, "choices")
    if choices:
        first = choices[0]
        message = _field(first, "message")
        content = _field(message, "content") if message is not None else _field(first, "text")
        if content is not None:
            return str(content)
    content = _field(response, "content")
    return "" if content is None else str(content)


def new_correlation_id() -> str:
    """Return a non-secret identifier suitable for joining related attempts."""
    return str(uuid.uuid4())


def resolve_metrics_path(project_root: str | Path | None = None) -> Path | None:
    """Resolve the opt-in evidence path without inventing a project location."""
    configured = os.environ.get("PLANFILE_LLM_METRICS_PATH")
    if configured and configured.strip():
        return Path(configured).expanduser()
    root = Path(project_root) if project_root is not None else Path.cwd()
    if (root / ".planfile").is_dir():
        return root / DEFAULT_METRICS_PATH
    return None


class MetricsStore:
    """Lock-protected JSONL store containing only redacted call receipts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def append(self, record: Mapping[str, Any]) -> None:
        if record.get("schema") != METRICS_SCHEMA:
            raise ValueError("llm_metrics_schema_invalid")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self.lock_path), timeout=30)
        with lock:
            existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
            _atomic_write_text(
                self.path,
                existing + json.dumps(dict(record), sort_keys=True, separators=(",", ":")) + "\n",
            )

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with FileLock(str(self.lock_path), timeout=30):
            lines = self.path.read_text(encoding="utf-8").splitlines()
        records: list[dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except (TypeError, ValueError) as exc:
                raise ValueError("llm_metrics_invalid_json") from exc
            if not isinstance(item, dict) or item.get("schema") != METRICS_SCHEMA:
                raise ValueError("llm_metrics_schema_invalid")
            records.append(item)
        return records

    def record_attempt(
        self,
        *,
        correlation_id: str,
        prompt: str,
        model: str,
        backend: str,
        attempt: int,
        started_at: str,
        latency_ms: float,
        status: str,
        response: object = None,
        error: BaseException | None = None,
    ) -> dict[str, Any]:
        """Create and persist a receipt; no raw provider data is retained."""
        if status not in {"succeeded", "failed"}:
            raise ValueError("llm_metrics_status_invalid")
        input_tokens, output_tokens, total_tokens = _usage(response)
        response_text = _response_content(response) if response is not None else ""
        stable = {
            "schema": METRICS_SCHEMA,
            "correlation_id": _safe_text(correlation_id, 96),
            "request_digest": _digest(prompt),
            "response_digest": _digest(response_text) if response is not None else None,
            "model": _safe_text(model),
            "backend": _safe_text(backend),
            "fallback": attempt > 1,
            "fallback_model": _safe_text(model) if attempt > 1 else None,
            "attempt": max(1, int(attempt)),
            "retry_count": max(0, int(attempt) - 1),
            "started_at": started_at,
            "latency_ms": round(max(0.0, float(latency_ms)), 3),
            "status": status,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": _response_cost(response) if response is not None else None,
            "error_type": _safe_text(type(error).__name__) if error is not None else None,
        }
        stable["receipt_id"] = _digest(
            json.dumps(stable, sort_keys=True, separators=(",", ":"))
        )
        record = {**stable, "recorded_at": datetime.now(timezone.utc).isoformat()}
        self.append(record)
        return record

    def export(self) -> dict[str, Any]:
        """Return a digest-bound aggregate suitable for a dashboard/export."""
        records = self.load()
        succeeded = [item for item in records if item.get("status") == "succeeded"]
        latencies = sorted(
            float(item["latency_ms"])
            for item in records
            if _finite_number(item.get("latency_ms")) is not None
        )

        def percentile(values: list[float], fraction: float) -> float | None:
            if not values:
                return None
            index = min(len(values) - 1, max(0, math.ceil(len(values) * fraction) - 1))
            return round(values[index], 3)

        def total(field: str) -> int | float | None:
            values = [_finite_number(item.get(field)) for item in records]
            known = [value for value in values if value is not None]
            return sum(known) if known else None

        return {
            "schema": EXPORT_SCHEMA,
            "calls": len(records),
            "succeeded": len(succeeded),
            "failed": len(records) - len(succeeded),
            "fallbacks": sum(1 for item in records if item.get("fallback")),
            "latency_ms": {"p50": percentile(latencies, 0.50), "p95": percentile(latencies, 0.95)},
            "tokens": {
                "input": total("input_tokens"),
                "output": total("output_tokens"),
                "total": total("total_tokens"),
            },
            "cost_usd": total("cost_usd"),
            "request_digests": sorted({item["request_digest"] for item in records if item.get("request_digest")}),
        }


def store_from_config(project_root: str | Path | None = None) -> MetricsStore | None:
    path = resolve_metrics_path(project_root)
    return MetricsStore(path) if path is not None else None


def elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


__all__ = [
    "DEFAULT_METRICS_PATH",
    "EXPORT_SCHEMA",
    "METRICS_SCHEMA",
    "MetricsStore",
    "elapsed_ms",
    "new_correlation_id",
    "resolve_metrics_path",
    "store_from_config",
]
