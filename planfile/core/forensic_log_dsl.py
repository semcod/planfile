"""Compact, human- and LLM-readable projection of Planfile SODL events."""

from __future__ import annotations

import json
from typing import Any

PREFIX = "PLOG/1"
SCHEMA = "planfile.forensic-log/v1"

_LOGIC_KEYS = (
    "name",
    "priority",
    "reason",
    "decision",
    "action",
    "changes",
    "previous_status",
    "status",
    "previous_execution_state",
    "execution_state",
    "outcome",
    "error",
    "message",
    "level",
    "queue",
    "collection",
    "idempotency_key",
)


def _bounded(value: Any) -> Any:
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, list):
        return [_bounded(item) for item in value[:30]]
    if isinstance(value, dict):
        return {str(key): _bounded(item) for key, item in list(value.items())[:30]}
    return value


def _logic(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else data
    logic = {
        key: _bounded(payload[key])
        for key in _LOGIC_KEYS
        if key in payload and payload[key] not in (None, "", [], {})
    }
    if "status" not in logic and event.get("status") not in (None, "", "recorded"):
        logic["status"] = event["status"]
    return logic


def project(event: dict[str, Any]) -> dict[str, Any]:
    """Return the bounded forensic fields that explain one operational event."""
    return {
        "schema": SCHEMA,
        "timestamp": str(event.get("timestamp") or "-"),
        "event_id": str(event.get("event_id") or "-"),
        "event_hash": str(event.get("event_hash") or "-"),
        "type": str(event.get("oql") or "observe"),
        "kind": str(event.get("kind") or "operation"),
        "ticket_id": str(event.get("ticket_id") or "-"),
        "actor": str(event.get("actor") or "system"),
        "source": str(event.get("source") or "planfile"),
        "mode": str(event.get("mode") or "observe"),
        "status": str(event.get("status") or "recorded"),
        "correlation_id": str(event.get("correlation_id") or "-"),
        "causation_id": str(event.get("causation_id") or "-"),
        "receipt_ref": str(event.get("receipt_ref") or "-"),
        "replayable": event.get("replayable") is not False,
        "logic": _logic(event),
    }


_FIELDS = (
    "timestamp",
    "event_id",
    "event_hash",
    "type",
    "kind",
    "ticket_id",
    "actor",
    "source",
    "mode",
    "status",
    "correlation_id",
    "causation_id",
    "receipt_ref",
    "replayable",
    "logic",
)


def serialize(event: dict[str, Any]) -> str:
    """Serialize one event as tab-delimited JSON values on a single line."""
    record = project(event)
    fields = [
        f"{key}={json.dumps(record[key], ensure_ascii=False, separators=(',', ':'))}"
        for key in _FIELDS
    ]
    return f"{PREFIX}\t" + "\t".join(fields)


def parse(line: str) -> dict[str, Any]:
    raw = str(line or "").rstrip("\r\n")
    if not raw.startswith(f"{PREFIX}\t"):
        raise ValueError("plog_prefix_invalid")
    values: dict[str, Any] = {"schema": SCHEMA}
    for token in raw.split("\t")[1:]:
        if "=" not in token:
            raise ValueError("plog_field_invalid")
        key, encoded = token.split("=", 1)
        try:
            values[key] = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise ValueError(f"plog_value_invalid:{key}") from exc
    if missing := set(_FIELDS) - values.keys():
        raise ValueError(f"plog_field_required:{sorted(missing)[0]}")
    canonical = f"{PREFIX}\t" + "\t".join(
        f"{key}={json.dumps(values[key], ensure_ascii=False, separators=(',', ':'))}"
        for key in _FIELDS
    )
    if canonical != raw:
        raise ValueError("plog_line_not_canonical")
    return values
