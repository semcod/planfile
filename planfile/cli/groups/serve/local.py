"""Serialize local serve startup and gracefully replace our recorded Linux process."""

import errno
import hashlib
import json
import os
import signal
import socket
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from .restart import RestartError, restart_container


def _process_start(pid: int) -> str:
    # comm may contain spaces and parentheses; field 22 is relative to its closing ')'.
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def _pidfd_open(pid: int) -> int:
    if hasattr(os, "pidfd_open"):
        return os.pidfd_open(pid)
    # Some Linux Python builds (including Conda) omit os.pidfd_open although
    # glibc and the kernel support it. Keep the same PID-reuse protection.
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.pidfd_open
    function.argtypes = [ctypes.c_int, ctypes.c_uint]
    function.restype = ctypes.c_int
    fd = function(pid, 0)
    if fd < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return fd


def _stop_recorded(record: Path, host: str, port: int) -> None:
    try:
        owner = json.loads(record.read_text())
        pid = owner["pid"]
        if (
            type(pid) is not int
            or pid <= 1
            or pid == os.getpid()
            or owner["host"] != host
            or owner["port"] != port
            or owner["project"] != str(Path.cwd().resolve())
            or Path(f"/proc/{pid}").stat().st_uid != os.getuid()
            or _process_start(pid) != owner["start"]
        ):
            raise ValueError("Owner mismatch")
        # A pidfd pins process identity even if the PID is recycled before signaling.
        fd = _pidfd_open(pid)
        try:
            if _process_start(pid) != owner["start"]:
                raise ValueError("Owner changed")
            signal.pidfd_send_signal(fd, signal.SIGTERM)
        finally:
            os.close(fd)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RestartError(
            f"Port {port} is occupied by an unverified service. Nothing was stopped. "
            "Stop it through its service manager or choose another port."
        ) from exc


def _bind(host: str, port: int) -> socket.socket:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    return socket.create_server((host, port), family=family)


@contextmanager
def serve_endpoint(host: str, port: int):
    """Yield (listening socket, restarted container); keep the socket through uvicorn exit."""
    if not sys.platform.startswith("linux"):
        # Free endpoints work everywhere; automatic process replacement needs pidfds.
        with _bind(host, port) as listener:
            yield listener, None
        return
    import fcntl

    host = socket.gethostbyname(host) if ":" not in host else host
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "planfile/serve"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()
    record = state / f"{key}.json"
    listener = None
    container_id = None
    with (state / f"{key}.lock").open("a") as lock:
        deadline = time.monotonic() + 30
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise RestartError(
                        "Another serve restart is in progress; retry after it finishes."
                    ) from exc
                time.sleep(0.1)
        try:
            listener = _bind(host, port)
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
            container_id = restart_container(host, port)
            if container_id is None:
                _stop_recorded(record, host, port)
                deadline = time.monotonic() + 15
                while True:
                    try:
                        listener = _bind(host, port)
                        break
                    except OSError as retry:
                        if retry.errno != errno.EADDRINUSE or time.monotonic() >= deadline:
                            raise RestartError(
                                "Previous Planfile server did not release the port in time."
                            ) from retry
                        time.sleep(0.1)
        if listener is not None:
            owner = {
                "pid": os.getpid(),
                "start": _process_start(os.getpid()),
                "host": host,
                "port": port,
                "project": str(Path.cwd().resolve()),
            }
            temporary = record.with_suffix(f".{os.getpid()}.tmp")
            try:
                temporary.write_text(json.dumps(owner))
                temporary.replace(record)
            except BaseException:
                listener.close()
                raise
    try:
        yield listener, container_id
    finally:
        if listener is not None:
            listener.close()
        # Leave a stale record on exit: identity validation rejects it, and a free
        # endpoint overwrites it. An old process must never remove its successor's record.
