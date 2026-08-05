"""Regression tests for the mtime-aware ``_read_yaml_cached`` invalidation.

Background: long-running planfile API server (``planfile.api.server``)
shares a single ``TicketStore`` instance across requests. When an
external writer (e.g. ``koru --queue`` running in a separate process)
modifies ``.planfile/sprints/current.yaml``, the in-memory cache must
be invalidated so the next HTTP request returns fresh ticket state.

Before the mtime-aware fix the cache key was just ``str(path)`` and
the entry was kept forever, so the panel at ``http://localhost:8765/``
served stale ``status=open`` even after koru had completed the ticket.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

from planfile.core.store_files import StoreFileMixin


class _Store(StoreFileMixin):
    """Minimal concrete store for testing the mixin in isolation."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir


def _write_sprint(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=True))


def test_cache_returns_data_on_first_read(tmp_path: Path) -> None:
    sprint = tmp_path / "current.yaml"
    _write_sprint(sprint, {"sprint": {"id": "s1", "tickets": {"PLF-1": {"status": "open"}}}})

    store = _Store(tmp_path)
    data = store._read_yaml_cached(sprint)

    assert data is not None
    assert data["sprint"]["tickets"]["PLF-1"]["status"] == "open"


def test_cache_hit_does_not_reread_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When mtime is unchanged, the YAML loader must NOT be invoked twice."""
    sprint = tmp_path / "current.yaml"
    _write_sprint(sprint, {"sprint": {"id": "s1", "tickets": {}}})
    store = _Store(tmp_path)

    # Prime cache.
    store._read_yaml_cached(sprint)

    load_calls = {"n": 0}
    real_load = yaml.safe_load

    def counting_load(text: str):
        load_calls["n"] += 1
        return real_load(text)

    monkeypatch.setattr(yaml, "safe_load", counting_load)
    store._read_yaml_cached(sprint)
    store._read_yaml_cached(sprint)
    store._read_yaml_cached(sprint)

    assert load_calls["n"] == 0, "Cache hit should not re-parse YAML"


def test_external_write_invalidates_cache_via_mtime(tmp_path: Path) -> None:
    """The whole point of the fix: external writers must be visible.

    We simulate koru --queue completing a ticket: it writes the YAML in
    a separate process, bumping mtime. The store (which still has the
    old payload cached) must return the fresh data on the next read.
    """
    sprint = tmp_path / "current.yaml"
    _write_sprint(sprint, {"sprint": {"tickets": {"PLF-1": {"status": "open"}}}})

    store = _Store(tmp_path)
    first = store._read_yaml_cached(sprint)
    assert first["sprint"]["tickets"]["PLF-1"]["status"] == "open"

    # Pause long enough for st_mtime_ns to differ on filesystems with
    # coarse timestamp granularity (some have only second resolution).
    time.sleep(0.01)
    _write_sprint(sprint, {"sprint": {"tickets": {"PLF-1": {"status": "done"}}}})
    # Defensive on coarse-grained filesystems.
    import os as _os
    later = sprint.stat().st_mtime + 1
    _os.utime(sprint, (later, later))

    second = store._read_yaml_cached(sprint)
    assert second["sprint"]["tickets"]["PLF-1"]["status"] == "done", (
        "External write must invalidate the cache via mtime check; "
        "got stale 'open' status which means the panel at :8765 would "
        "still show pre-koru state."
    )


def test_deleted_file_evicts_cache_entry(tmp_path: Path) -> None:
    sprint = tmp_path / "current.yaml"
    _write_sprint(sprint, {"sprint": {"id": "s1"}})

    store = _Store(tmp_path)
    assert store._read_yaml_cached(sprint) is not None

    sprint.unlink()
    assert store._read_yaml_cached(sprint) is None

    # Recreate and verify it reappears (not stuck on the deleted/None state).
    _write_sprint(sprint, {"sprint": {"id": "s2"}})
    fresh = store._read_yaml_cached(sprint)
    assert fresh is not None
    assert fresh["sprint"]["id"] == "s2"


def test_missing_file_returns_none_without_caching(tmp_path: Path) -> None:
    store = _Store(tmp_path)
    missing = tmp_path / "nope.yaml"

    assert store._read_yaml_cached(missing) is None
    assert store._read_yaml_cached(missing) is None


def test_large_yaml_is_readable_but_not_retained_in_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sprint = tmp_path / "archive-legacy.yaml"
    _write_sprint(sprint, {"sprint": {"id": "legacy", "tickets": {}}})
    store = _Store(tmp_path)
    store.MAX_CACHEABLE_YAML_BYTES = 1

    from planfile.core import fastio

    read_calls = {"n": 0}
    real_read = fastio.read_yaml_fast

    def counting_read(path: Path):
        read_calls["n"] += 1
        return real_read(path)

    monkeypatch.setattr(fastio, "read_yaml_fast", counting_read)

    assert store._read_yaml_cached(sprint)["sprint"]["id"] == "legacy"
    assert store._read_yaml_cached(sprint)["sprint"]["id"] == "legacy"
    assert str(sprint) not in store._yaml_cache
    assert read_calls["n"] == 2
