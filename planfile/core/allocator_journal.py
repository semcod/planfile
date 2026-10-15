"""Derived allocator evidence, maintained under the store mutation lock.

A cache is reusable only for the exact journal identity and stat revision.
Unknown writers, rotation and interrupted publication force a streaming rebuild.
The journal remains authoritative; cache write failure never fails a committed
journal append. Ticket and remote-sync high-water checks remain in the store.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

_ID = re.compile(r"^(.+)-(\d+)$")
_SCHEMA = "planfile.allocator-journal/v1"


class JournalHighwater:
    def __init__(self, journal: Path):
        self.journal = journal
        self.cache = journal.parent.parent / "index" / "allocator-journal.json"

    def signature(self):
        try:
            stat = self.journal.stat()
        except FileNotFoundError:
            return None
        return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def current(self):
        try:
            # Cache contains only prefix counters, not journal payloads.
            if self.cache.stat().st_size > 1_000_000:
                return None
            value = json.loads(self.cache.read_text(encoding="utf-8"))
            checksum = value.pop("checksum")
            if value.get("schema") != _SCHEMA or checksum != self.digest(value):
                return None
            highs = value["highs"]
            if not isinstance(highs, dict) or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in highs.items()):
                return None
            if value["signature"] != self.signature():
                return None
            return value
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def publish(self, signature, highs):
        value = {"schema": _SCHEMA, "signature": signature, "highs": highs}
        value["checksum"] = self.digest(value)
        temporary = None
        try:
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.cache.parent, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.cache)
        except OSError:
            # A missing/stale cache is rebuilt next time, never trusted by age.
            pass
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def include(highs, event):
        if not isinstance(event, dict):
            return
        match = _ID.fullmatch(str(event.get("ticket_id") or ""))
        if match:
            prefix, number = match.groups()
            highs[prefix] = max(highs.get(prefix, 0), int(number))

    def highwater(self, prefix):
        cached = self.current()
        if cached is not None:
            return cached["highs"].get(prefix, 0)
        signature = self.signature()
        highs = {}
        if signature is not None:
            # Do not retain hundreds of MiB of decoded events or cap history by
            # row count: an old deleted ticket can still own the largest ID.
            with self.journal.open(encoding="utf-8", errors="replace") as source:
                for line in source:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(row, dict):
                        self.include(highs, row.get("event"))
        if signature != self.signature():
            raise RuntimeError("allocator journal changed during locked scan")
        self.publish(signature, highs)
        return highs.get(prefix, 0)

    def appended(self, cached, events, byte_count):
        if cached is None:
            return
        before = cached["signature"]
        after = self.signature()
        if after is None:
            return
        expected_size = (before[2] if before is not None else 0) + byte_count
        if after[2] != expected_size or (before is not None and before[:2] != after[:2]):
            return
        highs = dict(cached["highs"])
        for event in events:
            self.include(highs, event)
        self.publish(after, highs)
