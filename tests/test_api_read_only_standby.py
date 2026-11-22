"""Tests for PLANFILE_READ_ONLY standby mode and GET /readyz (#459)."""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from planfile.api import server
from planfile.api.standby import is_read_only_mode, maintenance_disabled_for_standby
from planfile.core.store import TicketIndexContentionError


def _fake_pf(*, enabled: bool = True, current: bool = True, exc: Exception | None = None):
    class _FakeIndex:
        def is_current(self, signature: object) -> bool:
            if exc is not None:
                raise exc
            return current

    class _FakeStore:
        def ticket_index_enabled(self) -> bool:
            return enabled

        def _sqlite_ticket_index(self):
            return _FakeIndex()

        def _ticket_index_signature(self):
            return ("sig", 1)

    return SimpleNamespace(store=_FakeStore())


def test_standby_env_helpers_respect_read_only_and_explicit_flags() -> None:
    assert is_read_only_mode({}) is False
    assert is_read_only_mode({"PLANFILE_READ_ONLY": "0"}) is False
    assert is_read_only_mode({"PLANFILE_READ_ONLY": "1"}) is True
    assert is_read_only_mode({"PLANFILE_READ_ONLY": "true"}) is True
    assert maintenance_disabled_for_standby("PLANFILE_DISABLE_INDEX_MAINTENANCE", {}) is False
    assert maintenance_disabled_for_standby(
        "PLANFILE_DISABLE_INDEX_MAINTENANCE", {"PLANFILE_DISABLE_INDEX_MAINTENANCE": "1"}
    ) is True
    assert maintenance_disabled_for_standby("PLANFILE_DISABLE_INDEX_MAINTENANCE", {"PLANFILE_READ_ONLY": "1"}) is True


@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
def test_read_only_mode_rejects_mutating_http_methods_with_503(
    monkeypatch: pytest.MonkeyPatch, method: str,
) -> None:
    monkeypatch.setenv("PLANFILE_READ_ONLY", "1")
    monkeypatch.setattr(server, "get_planfile", lambda: _fake_pf(current=True))
    client = TestClient(server.app)

    resp = client.request(method, "/tickets", json={})
    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"] == "read_only_standby"
    assert body["retryable"] is True
    assert resp.headers.get("retry-after") == "5"

    health = client.get("/health")
    assert health.status_code == 200
    readyz = client.get("/readyz")
    assert readyz.status_code == 200
    assert readyz.json()["ready"] is True
    assert readyz.json()["read_only"] is True


def test_read_only_mode_disables_background_maintenance_and_watcher_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLANFILE_READ_ONLY", "1")
    events: list[dict] = []
    monkeypatch.setattr(server, "_remember_durable_event", lambda ev: events.append(ev))

    async def _run() -> None:
        await server._start_ticket_index_maintenance()
        await server._start_archive_maintenance()
        await server._start_planfile_watcher()

    asyncio.run(_run())
    assert server._ticket_index_maintenance_task is None
    assert server._archive_maintenance_task is None
    assert server._watch_task is None
    assert events == []


def test_readyz_reports_current_stale_and_unavailable_states(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLANFILE_READ_ONLY", raising=False)
    client = TestClient(server.app)

    monkeypatch.setattr(server, "get_planfile", lambda: _fake_pf(enabled=True, current=True))
    r_ok = client.get("/readyz")
    assert r_ok.status_code == 200
    assert r_ok.json() == {
        "status": "ready",
        "ready": True,
        "ticket_index_enabled": True,
        "ticket_index_current": True,
        "read_only": False,
    }

    monkeypatch.setattr(server, "get_planfile", lambda: _fake_pf(enabled=False))
    r_disabled = client.get("/readyz")
    assert r_disabled.status_code == 200
    assert r_disabled.json()["ticket_index_enabled"] is False

    monkeypatch.setattr(server, "get_planfile", lambda: _fake_pf(enabled=True, current=False))
    r_stale = client.get("/readyz")
    assert r_stale.status_code == 503
    assert r_stale.json()["reason"] == "ticket_index_stale"
    assert r_stale.headers.get("retry-after") == "2"

    for exc in (TicketIndexContentionError("busy"), sqlite3.OperationalError("locked")):
        monkeypatch.setattr(server, "get_planfile", lambda e=exc: _fake_pf(enabled=True, exc=e))
        r_unavail = client.get("/readyz")
        assert r_unavail.status_code == 503
        assert r_unavail.json()["reason"] == "ticket_index_unavailable"

    monkeypatch.setattr(server, "get_planfile", lambda: SimpleNamespace(store=None))
    r_nostore = client.get("/readyz")
    assert r_nostore.status_code == 503
    assert r_nostore.json()["reason"] == "store_unavailable"
