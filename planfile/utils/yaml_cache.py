"""Small YAML reads cached by path and modification time.

Shared by modules that re-read the same configuration file in a loop. The cache key includes
``st_mtime_ns``, so an edited file is parsed again; it is a read cache, not a source of truth.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=256)
def _load_yaml_cached(path_str: str, mtime_ns: int) -> object:
    return yaml.safe_load(Path(path_str).read_text(encoding="utf-8"))


def read_yaml_file(path: Path) -> object:
    """Parse ``path`` with ``yaml.safe_load``; repeated reads of an unchanged file are cached."""
    stat = path.stat()
    return _load_yaml_cached(str(path.resolve()), stat.st_mtime_ns)
