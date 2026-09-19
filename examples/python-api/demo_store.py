"""Disposable stores for the synchronous Python API demonstrations."""

import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory

from planfile import Planfile

_active_demo = ContextVar("active_planfile_demo", default=None)


@contextmanager
def demo_store():
    """Keep nested examples in one temporary store; restore cwd even on failure."""
    if _active_demo.get() is not None:
        yield _active_demo.get()
        return
    original = Path.cwd()
    with TemporaryDirectory(prefix="planfile-demo-") as directory:
        root = Path(directory).resolve()
        # Initialize explicitly before auto-discovery can inspect any parent.
        Planfile(str(root))
        reset_marker = _active_demo.set(root)
        try:
            os.chdir(root)
            print(f"Disposable demo store: {root}")
            yield root
        finally:
            os.chdir(original)
            _active_demo.reset(reset_marker)


def isolated_demo(function):
    """Run a CLI entry point or imported example in a disposable local store."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with demo_store():
            return function(*args, **kwargs)
    return wrapped
