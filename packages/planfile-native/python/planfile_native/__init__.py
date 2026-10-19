"""planfile-native: Rust storage kernel for planfile.

The compiled extension is optional. ``AVAILABLE`` tells callers whether it could be imported;
when it is False they use their pure-Python implementation.
"""

from __future__ import annotations

try:
    from . import _native
    from ._native import (  # noqa: F401
        Unsupported,
        atomic_write_text,
        dump_json,
        dump_yaml,
        normalize,
        write_sprint,
    )

    __version__ = _native.__version__
    AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the compiled wheel
    AVAILABLE = False
    __version__ = "0.0.0"

__all__ = [
    "AVAILABLE",
    "Unsupported",
    "__version__",
    "atomic_write_text",
    "dump_json",
    "dump_yaml",
    "normalize",
    "write_sprint",
]
