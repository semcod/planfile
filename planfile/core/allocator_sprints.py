"""Derived identity evidence for file-backed sprint archives."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from planfile.core.fastio import load_yaml_text


def signature(path: Path) -> list[int]:
    stat = path.stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]


def record_highwater(records, prefix: str) -> int:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    marker = re.compile(rf"{re.escape(prefix)}-(\d+)")
    highest = 0
    for record in records:
        match = pattern.fullmatch(str(record.get("id") or ""))
        if match:
            highest = max(highest, int(match.group(1)))
        for label in record.get("labels") or []:
            match = marker.search(str(label))
            if match:
                highest = max(highest, int(match.group(1)))
        description = record.get("description") or ""
        if f"{prefix}-" in description:
            for match in marker.finditer(description):
                highest = max(highest, int(match.group(1)))
    return highest


def records(data):
    if not isinstance(data, dict):
        return
    root = data.get("sprint")
    root = root if isinstance(root, dict) else data
    tickets = root.get("tickets")
    found = False
    if isinstance(tickets, dict):
        for key, record in tickets.items():
            if isinstance(record, dict):
                found = True
                yield record if "id" in record else dict(record, id=str(key))
    if not found and isinstance(root.get("tasks"), list):
        for index, task in enumerate(root["tasks"], 1):
            if isinstance(task, dict):
                yield task if "id" in task else dict(task, id=f"TSK-{index:03d}")


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


MAX_LOCKED_REBUILD_BYTES = 5_000_000


def sprint_highwater(source: Path, prefix: str, *, max_rebuild_bytes: int | None = None) -> int:
    """Read compact evidence; rebuild directly from source on any invalidation.

    Preparation may run outside the mutation lock. Allocation callers must
    revalidate source identity under their lock and bound cold reconstruction.
    Changes during a rebuild fail rather than publishing mismatched evidence.
    JSON mirrors and the store's object cache are deliberately not consulted.
    """
    before = signature(source)
    key = hashlib.sha256((source.name + "\0" + prefix).encode()).hexdigest()
    cache = source.parent / "index" / "allocator-sprints" / f"{key}.json"
    try:
        value = json.loads(cache.read_text(encoding="utf-8"))
        checksum = value.pop("checksum")
        if (value.get("version") == 1 and value.get("signature") == before
                and value.get("prefix") == prefix and value.get("source") == source.name
                and type(value.get("highest")) is int and value["highest"] >= 0
                and _digest(value) == checksum and signature(source) == before):
            return value["highest"]
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        pass
    if max_rebuild_bytes is not None and before[2] > max_rebuild_bytes:
        raise RuntimeError("allocator_evidence_changed_retry: " + source.name)
    if max_rebuild_bytes is None:
        text = source.read_text(encoding="utf-8")
    else:
        # Bound the read too: an uncoordinated writer may grow or replace the
        # source after stat, before open. Never read that large file under lock.
        with source.open("rb") as stream:
            raw = stream.read(max_rebuild_bytes + 1)
        if len(raw) > max_rebuild_bytes:
            raise RuntimeError("allocator_evidence_changed_retry: " + source.name)
        text = raw.decode("utf-8")
    data = load_yaml_text(text)
    highest = record_highwater(records(data), prefix)
    if signature(source) != before:
        raise RuntimeError("Sprint changed while rebuilding allocator identity evidence")
    value = {"version": 1, "signature": before, "prefix": prefix, "source": source.name, "highest": highest}
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
        pass  # Derived cache failure must not prevent allocation.
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return highest
