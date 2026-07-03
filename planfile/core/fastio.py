"""Fast read/write layer for sprint YAML files.

Problem: a busy project accumulates a 40k-line ``current.yaml``; parsing it
with pure-Python ``yaml.safe_load`` costs ~2 s per read, and *every* CLI
invocation (``planfile ticket list`` runs many times per koru cycle) plus the
dashboard pays it again.

Two layers, YAML stays the single source of truth:

1. libyaml loaders/dumpers (``CSafeLoader``/``CSafeDumper``) — ~10× faster
   parse when available.
2. A self-healing JSON mirror (``<file>.fast.json``) written next to every
   sprint YAML. It embeds the YAML's post-write ``mtime_ns``; a reader uses
   the mirror only when it still matches the YAML's current mtime, so
   external/manual YAML edits simply invalidate it. Reading the mirror is
   ~300× faster than the pure-Python parse (7 ms vs 2 s on 660 tickets).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

try:  # libyaml (10x faster); graceful fallback to pure python
    from yaml import CSafeLoader as FastLoader
    from yaml import CSafeDumper as FastDumper
except ImportError:  # pragma: no cover - environment without libyaml
    from yaml import SafeLoader as FastLoader
    from yaml import SafeDumper as FastDumper

_MIRROR_SUFFIX = ".fast.json"
_MIRROR_VERSION = 1


def mirror_path(path: Path) -> Path:
    return path.with_name(path.name + _MIRROR_SUFFIX)


def load_yaml_text(text: str) -> Any:
    return yaml.load(text, Loader=FastLoader)


def dump_yaml(data: Any, *, allow_unicode: bool = False) -> str:
    return yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=allow_unicode,
        Dumper=FastDumper,
    )


def _stat_mtime_ns(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def write_mirror(yaml_path: Path, data: Any) -> None:
    """Persist the JSON mirror for ``yaml_path`` (best-effort, never raises)."""
    mtime_ns = _stat_mtime_ns(yaml_path)
    if mtime_ns is None:
        return
    payload = {"version": _MIRROR_VERSION, "yaml_mtime_ns": mtime_ns, "data": data}
    try:
        _atomic_write_text(mirror_path(yaml_path), json.dumps(payload, ensure_ascii=False))
    except Exception:
        # The mirror is an optimization only; a failed write must never
        # break a ticket mutation. Readers fall back to parsing the YAML.
        pass


def read_mirror(yaml_path: Path, yaml_mtime_ns: int) -> Any | None:
    """Return mirrored data when it matches the YAML's current mtime."""
    try:
        raw = mirror_path(yaml_path).read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != _MIRROR_VERSION:
        return None
    if payload.get("yaml_mtime_ns") != yaml_mtime_ns:
        return None  # YAML changed (external edit) — mirror is stale
    return payload.get("data")


def read_yaml_fast(path: Path) -> Any | None:
    """Read a sprint YAML via mirror when fresh; parse + heal mirror otherwise.

    Returns None when the file is missing or unparsable.
    """
    mtime_ns = _stat_mtime_ns(path)
    if mtime_ns is None:
        return None
    mirrored = read_mirror(path, mtime_ns)
    if mirrored is not None:
        return mirrored
    try:
        data = load_yaml_text(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    write_mirror(path, data)
    return data
