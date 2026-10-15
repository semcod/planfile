"""Compact, derived live-key evidence for file-backed sprint deduplication."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from planfile.core.allocator_sprints import records, signature
from planfile.core.fastio import load_yaml_text


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _valid_records(value) -> bool:
    return isinstance(value, list) and all(
        isinstance(row, dict) and set(row) == {"id", "created_at", "labels"}
        and isinstance(row["id"], str) and isinstance(row["created_at"], str)
        and isinstance(row["labels"], list)
        and all(isinstance(label, str) and label.startswith("dedupe:") for label in row["labels"])
        for row in value
    )


def live_records(source: Path, *, max_rebuild_bytes: int | None = None) -> list[dict]:
    """Use exact source identity or rebuild from YAML, never an mtime-only mirror."""
    before = signature(source)
    key = hashlib.sha256(source.name.encode()).hexdigest()
    cache = source.parent / "index" / "allocator-dedupe" / f"{key}.json"
    try:
        value = json.loads(cache.read_text(encoding="utf-8"))
        checksum = value.pop("checksum")
        if (value.get("version") == 1 and value.get("source") == source.name
                and value.get("signature") == before and _valid_records(value.get("records"))
                and _digest(value) == checksum and signature(source) == before):
            return value["records"]
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        pass
    if max_rebuild_bytes is not None and before[2] > max_rebuild_bytes:
        raise RuntimeError("dedupe_evidence_changed_retry: " + source.name)
    if max_rebuild_bytes is None:
        text = source.read_text(encoding="utf-8")
    else:
        with source.open("rb") as stream:
            raw = stream.read(max_rebuild_bytes + 1)
        if len(raw) > max_rebuild_bytes:
            raise RuntimeError("dedupe_evidence_changed_retry: " + source.name)
        text = raw.decode("utf-8")
    live = []
    for row in records(load_yaml_text(text)):
        if str(row.get("status") or "") in {"done", "canceled"}:
            continue
        labels = [label for label in row.get("labels") or []
                  if isinstance(label, str) and label.startswith("dedupe:")]
        if labels:
            live.append({"id": str(row.get("id") or ""),
                         "created_at": str(row.get("created_at") or ""), "labels": labels})
    if signature(source) != before:
        raise RuntimeError("Sprint changed while rebuilding dedupe identity evidence")
    value = {"version": 1, "source": source.name, "signature": before, "records": live}
    value["checksum"] = _digest(value)
    temporary = None
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=cache.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, cache)
    except OSError:
        pass  # Optional derived evidence cannot prevent a safe allocation.
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return live
