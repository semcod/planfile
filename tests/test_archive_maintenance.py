from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from planfile.api import server


def test_daily_maintenance_runs_history_sweep_immediately(monkeypatch):
    calls = []

    class FakeStore:
        def archive_completed(self):
            calls.append("archive")
            return {
                "triggered": True,
                "archived": 2,
                "remaining": 1,
                "archive_files": ["history-2026-08-04"],
            }

    async def stop_after_first_iteration(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        server,
        "get_planfile",
        lambda: SimpleNamespace(store=FakeStore()),
    )
    monkeypatch.setattr(server.asyncio, "sleep", stop_after_first_iteration)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server._archive_history_daily(interval_seconds=0))

    assert calls == ["archive"]
    assert any(event.get("action") == "daily-history" for event in server._event_history)
