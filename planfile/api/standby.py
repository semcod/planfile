"""Read-only standby mode and readiness probe helpers for Blue/Green & canary deployments."""
from __future__ import annotations

from collections.abc import Mapping
import os
import sqlite3
from typing import Any

from planfile.core.store import StoreLockTimeoutError, TicketIndexContentionError

MUTATING_HTTP_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})
READ_ONLY_RETRY_AFTER_SECONDS = 5
_TRUTHY_FLAGS = frozenset({"1", "true", "yes", "on"})


def is_read_only_mode(environ: Mapping[str, str] | None = None) -> bool:
    """Return True when ``PLANFILE_READ_ONLY`` enables read-only standby mode."""
    env = os.environ if environ is None else environ
    return str(env.get("PLANFILE_READ_ONLY", "")).strip().lower() in _TRUTHY_FLAGS


def maintenance_disabled_for_standby(env_var: str, environ: Mapping[str, str] | None = None) -> bool:
    """Return True when standby mode or ``env_var=1`` disables a background writer loop."""
    env = os.environ if environ is None else environ
    return is_read_only_mode(env) or str(env.get(env_var, "")).strip() == "1"


def read_only_rejection_payload() -> dict[str, Any]:
    """Return the structured retryable 503 payload for mutating requests on standby."""
    return {
        "detail": "read_only_standby",
        "code": "read_only_standby",
        "retryable": True,
        "retry_after_seconds": READ_ONLY_RETRY_AFTER_SECONDS,
    }


def evaluate_readiness(
    pf: Any,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Return ``(http_status, payload)`` reflecting store & SQLite index readiness."""
    read_only = is_read_only_mode(environ)
    store = getattr(pf, "store", None)
    if store is None:
        return (
            503,
            {
                "status": "not_ready",
                "ready": False,
                "reason": "store_unavailable",
                "retryable": True,
                "read_only": read_only,
            },
        )
    if callable(getattr(store, "ticket_index_enabled", None)) and store.ticket_index_enabled():
        try:
            index = store._sqlite_ticket_index()
            signature = store._ticket_index_signature()
            current = bool(index.is_current(signature))
        except (sqlite3.DatabaseError, OSError, TicketIndexContentionError, StoreLockTimeoutError):
            return (
                503,
                {
                    "status": "not_ready",
                    "ready": False,
                    "reason": "ticket_index_unavailable",
                    "retryable": True,
                    "ticket_index_enabled": True,
                    "ticket_index_current": False,
                    "read_only": read_only,
                },
            )
        if not current:
            return (
                503,
                {
                    "status": "not_ready",
                    "ready": False,
                    "reason": "ticket_index_stale",
                    "retryable": True,
                    "ticket_index_enabled": True,
                    "ticket_index_current": False,
                    "read_only": read_only,
                },
            )
        return (
            200,
            {
                "status": "ready",
                "ready": True,
                "ticket_index_enabled": True,
                "ticket_index_current": True,
                "read_only": read_only,
            },
        )
    return (
        200,
        {
            "status": "ready",
            "ready": True,
            "ticket_index_enabled": False,
            "ticket_index_current": True,
            "read_only": read_only,
        },
    )
