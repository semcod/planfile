from __future__ import annotations

from pathlib import Path
from typing import Any


class StoreFileMixin:
    # Keep hot operational and small daily-history snapshots cached, but do not
    # pin legacy multi-megabyte archives in long-running API workers. Those
    # files remain readable on demand and can be migrated independently.
    MAX_CACHEABLE_YAML_BYTES = 5_000_000

    def _sprint_file(self, sprint: str) -> Path:
        return self.base_dir / f"{sprint}.yaml"

    def _all_sprint_files(self) -> list[Path]:
        return sorted(self.base_dir.glob("*.yaml"))

    def _yaml_file_cacheable(self, path: Path) -> bool:
        try:
            return path.stat().st_size <= self.MAX_CACHEABLE_YAML_BYTES
        except OSError:
            return False

    def _read_yaml_cached(self, path: Path) -> dict[str, Any] | None:
        """Read a YAML sprint file with mtime-aware caching.

        The cache is keyed by ``(path, mtime_ns)`` so that external
        writers (e.g. ``koru --queue`` running in a separate process)
        invalidate the cache automatically. Without the mtime check the
        long-running ``planfile.api.server`` would serve stale ticket
        state until the uvicorn worker restarted.
        """
        cached = getattr(self, "_yaml_cache", None)
        if cached is None:
            cached = {}
            self._yaml_cache = cached
        key = str(path)
        if not path.exists():
            cached.pop(key, None)
            return None
        try:
            stat = path.stat()
            mtime_ns = stat.st_mtime_ns
            cacheable = stat.st_size <= self.MAX_CACHEABLE_YAML_BYTES
        except OSError:
            mtime_ns = -1
            cacheable = False
        if not cacheable:
            cached.pop(key, None)
            from planfile.core.fastio import read_yaml_fast

            return read_yaml_fast(path)
        entry = cached.get(key)
        if entry is not None and entry[0] == mtime_ns:
            return entry[1]
        from planfile.core.fastio import read_yaml_fast

        data = read_yaml_fast(path)
        cached[key] = (mtime_ns, data)
        return data
