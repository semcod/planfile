from __future__ import annotations

from pathlib import Path
from typing import Any


class StoreFileMixin:
    def _sprint_file(self, sprint: str) -> Path:
        return self.base_dir / f"{sprint}.yaml"

    def _all_sprint_files(self) -> list[Path]:
        return sorted(self.base_dir.glob("*.yaml"))

    def _read_yaml_cached(self, path: Path) -> dict[str, Any] | None:
        cached = getattr(self, "_yaml_cache", None)
        if cached is None:
            cached = {}
            self._yaml_cache = cached
        key = str(path)
        if key in cached:
            return cached[key]
        if not path.exists():
            cached[key] = None
            return None
        try:
            import yaml
            data = yaml.safe_load(path.read_text()) or {}
        except Exception:
            data = None
        cached[key] = data
        return data
