from __future__ import annotations

import asyncio
import fcntl
import inspect
import logging
import threading
import time

import anyio.to_thread
import httpx
import pytest

from planfile import Planfile
from planfile.api import server
from planfile.core import sqlite_index


def _setup_store(tmp_path):
    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    pf.store._write_config(config)
    return pf


def test_health_endpoint_is_async_and_responds_when_threadpool_is_exhausted():
    assert inspect.iscoroutinefunction(server.health)

    blocker_started = threading.Event()
    release_blocker = threading.Event()

    def occupy_only_worker() -> None:
        blocker_started.set()
        release_blocker.wait(timeout=5.0)

    async def exercise() -> dict:
        limiter = anyio.to_thread.current_default_thread_limiter()
        original_tokens = limiter.total_tokens
        limiter.total_tokens = 1
        try:
            worker_task = asyncio.create_task(
                anyio.to_thread.run_sync(occupy_only_worker)
            )
            await asyncio.to_thread(blocker_started.wait, 2.0)
            transport = httpx.ASGITransport(app=server.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                response = await asyncio.wait_for(client.get("/health"), timeout=1.0)
            release_blocker.set()
            await worker_task
            assert response.status_code == 200
            return response.json()
        finally:
            release_blocker.set()
            limiter.total_tokens = original_tokens

    payload = asyncio.run(exercise())
    assert payload["status"] == "ok"
    assert "ticket.discovery.current_scoped_pages" in payload["capabilities"]


def test_background_index_maintenance_coalesces_active_rebuild_lock_without_blocking(
    tmp_path, monkeypatch, caplog
):
    pf = _setup_store(tmp_path)
    pf.create_ticket(name="Stale index entry")
    pf.store.configure_ticket_index(True)
    # Invalidate SQLite projection so _maintain_ticket_index attempts repair.
    pf.store._ticket_index_invalidation_path.write_text("stale-token", encoding="ascii")

    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    lock_path = pf.store._ticket_index_rebuild_lock_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            started = time.monotonic()
            coalesced = server._repair_ticket_index()
            elapsed = time.monotonic() - started
            assert coalesced == {"rebuilt": False, "coalesced": True}
            assert elapsed < 0.5

            ticks = 0

            async def fast_tick(_interval: float) -> None:
                nonlocal ticks
                ticks += 1
                if ticks >= 2:
                    raise asyncio.CancelledError

            monkeypatch.setattr(asyncio, "sleep", fast_tick)
            with caplog.at_level(logging.WARNING, logger="planfile.api"):
                with pytest.raises(asyncio.CancelledError):
                    asyncio.run(server._maintain_ticket_index(interval_seconds=0.01))

            assert ticks == 2
            assert not [
                rec
                for rec in caplog.records
                if "ticket index background repair failed" in rec.getMessage()
            ]
        finally:
            fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)


def test_sqlite_index_checkpoints_and_truncates_wal_after_rebuild_without_blocking_readers(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(sqlite_index, "_WAL_JOURNAL_SIZE_LIMIT_BYTES", 4096)
    pf = _setup_store(tmp_path)
    for idx in range(25):
        pf.create_ticket(name=f"Ticket {idx}", description="x" * 4096)
    pf.store.configure_ticket_index(True)

    index = pf.store._sqlite_ticket_index()
    wal_path = index.path.with_name(index.path.name + "-wal")
    report = pf.store.ensure_ticket_index(force=True)
    assert report["rebuilt"] is True
    if wal_path.exists():
        assert wal_path.stat().st_size <= 4096

    # Holding an open read snapshot must not cause rebuild's post-commit
    # checkpoint to block for SQLite's default 10s busy_timeout.
    with index._connection() as reader:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM tickets").fetchone()
        started = time.monotonic()
        rebuilt_under_reader = pf.store.ensure_ticket_index(force=True)
        elapsed = time.monotonic() - started
        assert rebuilt_under_reader["rebuilt"] is True
        assert elapsed < 2.0
