"""Durable, repository-bound receipts for external ticket publication.

The receipt log is deliberately separate from the sync mapping.  Mappings tell
the next run which remote object to update; receipts tell it whether an exact
payload was already published.  Both are local evidence and contain no
credentials or raw provider responses.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from filelock import FileLock

from planfile.core.fastio import _atomic_write_text
from planfile.sync.state import normalize_repository

RECEIPT_SCHEMA = "planfile.sync-receipt/v1"
_BACKEND = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")


class SyncReceiptConflict(ValueError):
    """A receipt key was reused for a different remote result."""


def _safe_url(value: object) -> str | None:
    """Keep only a remote URL's origin/path; query strings may contain tokens."""
    if not value:
        return None
    raw = str(value).strip()
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return None
    hostname = parts.hostname
    if not hostname:
        return None
    netloc = hostname.lower()
    try:
        port = parts.port
    except ValueError:
        return None
    if port:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, "", ""))


def _safe_text(value: object, limit: int = 512) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\x00", " ")
    return text[:limit] or None


def publish_intent(
    ticket_id: str,
    ticket: dict,
    integration: str,
    repository: str | None,
) -> dict:
    """Build the digest-bound identity of one outbound payload."""
    normalized_repo = normalize_repository(repository) if repository else None
    payload = {
        "name": _safe_text(ticket.get("name") or ticket.get("title")),
        "body": _safe_text(ticket.get("description") or ticket.get("body"), 4096),
        "status": _safe_text(ticket.get("status")),
        "labels": sorted({_safe_text(item, 128) for item in ticket.get("labels") or [] if _safe_text(item, 128)}),
        "priority": _safe_text(ticket.get("priority")),
        "assignee": _safe_text(ticket.get("assignee")),
    }
    payload_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()
    target = normalized_repo or "unbound"
    key = f"{integration}:{target}:{ticket_id}:{payload_digest}"
    return {
        "idempotency_key": key,
        "payload_digest": payload_digest,
        "integration": integration,
        "repository": normalized_repo,
        "ticket_id": str(ticket_id),
        "payload": payload,
    }


def receipt_path(planfile_dir: Path, integration: str) -> Path:
    backend = str(integration).strip()
    if not _BACKEND.fullmatch(backend):
        raise ValueError("sync_receipt_integration_invalid")
    return Path(planfile_dir) / "sync" / f"{backend}.receipts.jsonl"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OSError(f"sync_receipt_read_failed: {path}") from exc
    records: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (TypeError, ValueError) as exc:
            raise ValueError("sync_receipt_invalid_json") from exc
        if not isinstance(value, dict) or value.get("schema") != RECEIPT_SCHEMA:
            raise ValueError("sync_receipt_schema_invalid")
        records.append(value)
    return records


def successful_receipt(planfile_dir: Path, integration: str, idempotency_key: str) -> dict | None:
    """Return a prior success for an exact payload, if one exists."""
    path = receipt_path(planfile_dir, integration)
    lock = FileLock(str(path.with_suffix(path.suffix + ".lock")), timeout=30)
    with lock:
        records = _read(path)
    return next(
        (
            item
            for item in reversed(records)
            if item.get("idempotency_key") == idempotency_key
            and item.get("outcome") == "succeeded"
        ),
        None,
    )


def record_receipt(
    planfile_dir: Path,
    intent: dict,
    *,
    operation: str,
    outcome: str,
    remote_id: str | None = None,
    remote_url: str | None = None,
    remote_key: str | None = None,
    error_type: str | None = None,
) -> tuple[dict, bool]:
    """Append one receipt under a lock, deduplicating exact prior attempts."""
    if operation not in {"create", "update"}:
        raise ValueError("sync_receipt_operation_invalid")
    if outcome not in {"succeeded", "failed"}:
        raise ValueError("sync_receipt_outcome_invalid")
    key = str(intent.get("idempotency_key") or "").strip()
    if not key:
        raise ValueError("sync_receipt_key_required")
    safe_remote_id = _safe_text(remote_id, 256)
    safe_remote_url = _safe_url(remote_url)
    safe_remote_key = _safe_text(remote_key, 256)
    path = receipt_path(planfile_dir, str(intent.get("integration") or ""))
    lock = FileLock(str(path.with_suffix(path.suffix + ".lock")), timeout=30)
    with lock:
        records = _read(path)
        prior = [item for item in records if item.get("idempotency_key") == key]
        for item in reversed(prior):
            if item.get("outcome") == "succeeded":
                # A later success with another remote object would indicate a
                # duplicate create or a poisoned mapping; never hide it.
                if any(
                    value
                    and item.get(field)
                    and value != item.get(field)
                    for field, value in (
                        ("remote_id", safe_remote_id),
                        ("remote_url", safe_remote_url),
                        ("remote_key", safe_remote_key),
                    )
                ):
                    raise SyncReceiptConflict("sync_receipt_remote_conflict")
                return item, False
            if item.get("outcome") == outcome and all(
                not value or not item.get(field) or value == item.get(field)
                for field, value in (
                    ("remote_id", safe_remote_id),
                    ("remote_url", safe_remote_url),
                    ("remote_key", safe_remote_key),
                )
            ):
                return item, False

        attempt = max((int(item.get("attempt", 0)) for item in prior), default=0) + 1
        stable = {
            "schema": RECEIPT_SCHEMA,
            "idempotency_key": key,
            "payload_digest": str(intent.get("payload_digest") or ""),
            "integration": str(intent.get("integration") or ""),
            "repository": intent.get("repository"),
            "ticket_id": str(intent.get("ticket_id") or ""),
            "operation": operation,
            "outcome": outcome,
            "attempt": attempt,
            "remote_id": safe_remote_id,
            "remote_url": safe_remote_url,
            "remote_key": safe_remote_key,
            "error_type": _safe_text(error_type, 128) if outcome == "failed" else None,
        }
        stable["receipt_id"] = hashlib.sha256(
            json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "utf-8"
            )
        ).hexdigest()
        event = {
            **stable,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "".join(f"{json.dumps(item, sort_keys=True)}\n" for item in records)
        content += f"{json.dumps(event, sort_keys=True)}\n"
        _atomic_write_text(path, content)
        return event, True


__all__ = [
    "RECEIPT_SCHEMA",
    "SyncReceiptConflict",
    "publish_intent",
    "receipt_path",
    "record_receipt",
    "successful_receipt",
]
