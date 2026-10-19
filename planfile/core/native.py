"""Optional Rust storage kernel (``planfile-native``) behind a fail-closed switch.

Every helper returns ``None`` when the native path is disabled, not installed, or refuses the
value (``planfile_native.Unsupported``). Callers then run their pure-Python implementation, so
the result is always the one PyYAML would have produced.

``PLANFILE_NATIVE``
    ``auto`` (default) use the extension when importable; ``off`` never use it; ``verify`` use it
    and compare every YAML document with PyYAML's, raising ``RuntimeError`` on a mismatch.
``PLANFILE_NATIVE_FSYNC``
    ``0``/``false``/``off``/``no`` skips fsync of native writes; any other value keeps it.
"""

from __future__ import annotations

import os
from typing import Any

try:
    import planfile_native as _rs

    _AVAILABLE = bool(_rs.AVAILABLE)
except ImportError:  # pragma: no cover - extension is optional
    _rs = None
    _AVAILABLE = False

MODE_ENV = "PLANFILE_NATIVE"
FSYNC_ENV = "PLANFILE_NATIVE_FSYNC"
_FALSE_WORDS = frozenset({"0", "false", "off", "no"})
_MODES = frozenset({"auto", "off", "verify"})


def mode() -> str:
    """Effective mode; unknown values fail closed to ``off``."""
    value = os.environ.get(MODE_ENV, "auto").strip().lower() or "auto"
    return value if value in _MODES else "off"


def available() -> bool:
    return _AVAILABLE


def enabled() -> bool:
    return _AVAILABLE and mode() != "off"


def fsync_enabled() -> bool:
    return os.environ.get(FSYNC_ENV, "1").strip().lower() not in _FALSE_WORDS


def _verify(data: Any, allow_unicode: bool, native_text: str) -> None:
    from planfile.core.fastio import dump_yaml_python

    expected = dump_yaml_python(data, allow_unicode=allow_unicode)
    if expected != native_text:
        raise RuntimeError(
            "planfile-native YAML output differs from PyYAML; set PLANFILE_NATIVE=off "
            "and report this document shape"
        )


def dump_yaml(data: Any, *, allow_unicode: bool = False) -> str | None:
    if not enabled():
        return None
    try:
        text = _rs.dump_yaml(data, allow_unicode)
    except _rs.Unsupported:
        return None
    if mode() == "verify":
        _verify(data, allow_unicode, text)
    return text


def normalize(value: Any) -> Any | None:
    """``fastio._json_safe`` result, or ``None`` when the native path is not in use."""
    if not enabled():
        return None
    return _rs.normalize(value)


def write_sprint(
    path: Any,
    data: Any,
    *,
    allow_unicode: bool,
    mirror_version: int,
    mirror_suffix: str,
) -> tuple[int, str | None] | None:
    """Write YAML + JSON mirror natively; ``None`` means "use the Python writer"."""
    if not enabled():
        return None
    if mode() == "verify" and dump_yaml(data, allow_unicode=allow_unicode) is None:
        return None
    try:
        return _rs.write_sprint(
            os.fspath(path),
            data,
            allow_unicode,
            mirror_version,
            mirror_suffix,
            fsync_enabled(),
        )
    except _rs.Unsupported:
        return None
