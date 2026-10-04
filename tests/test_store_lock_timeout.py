from __future__ import annotations

import multiprocessing
import os
import time

import pytest

from planfile.core.store import Store, StoreLockTimeoutError

pytest.importorskip("fcntl")


def _hold_lock(path, ready, release):
    import fcntl

    with open(path, "a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        ready.set()
        release.wait(10)


@pytest.mark.parametrize("index", [False, True])
@pytest.mark.parametrize("crash", [False, True])
def test_contention_is_bounded_preserves_data_and_recovers(tmp_path, index, crash):
    store = Store(tmp_path)
    store.LOCK_TIMEOUT_SECONDS = 0.1
    store.base_dir.mkdir()
    data = store.base_dir / "tickets.yaml"
    data.write_text("ticket: unchanged\n")
    lock_path = store._ticket_index_rebuild_lock_path if index else store._lock_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    holder = context.Process(target=_hold_lock, args=(str(lock_path), ready, release))
    terminated = False
    holder.start()
    try:
        assert ready.wait(5)
        inode = lock_path.stat().st_ino
        acquire = store.ticket_index_rebuild_lock if index else store.mutation_lock
        for _ in range(2):
            started = time.monotonic()
            with pytest.raises(StoreLockTimeoutError, match="planfile_store_lock_timeout") as error:
                with acquire():
                    data.write_text("unsafe overwrite")
            assert time.monotonic() - started < 2
            assert str(lock_path) in str(error.value)
            assert "handoff" in str(error.value)
            assert lock_path.stat().st_ino == inode
            assert holder.is_alive()
            assert data.read_text() == "ticket: unchanged\n"
        if crash:
            holder.terminate()  # Only this test's child, never an existing owner.
            terminated = True
        else:
            release.set()
        holder.join(5)
        assert not holder.is_alive()
        with acquire():
            assert data.read_text() == "ticket: unchanged\n"
            data.write_text("ticket: recovered\n")
        assert data.read_text() == "ticket: recovered\n"
        assert lock_path.stat().st_ino == inode
    finally:
        # Terminating Event.wait can leave its multiprocessing condition locked.
        # The crash case must not reuse that child's synchronization primitive.
        if not terminated:
            release.set()
        holder.join(5)
        if holder.is_alive():
            holder.terminate()
            holder.join(5)


def test_nested_acquisition_times_out_without_unlocking_outer_owner(tmp_path):
    store = Store(tmp_path)
    store.LOCK_TIMEOUT_SECONDS = 0.05
    with store.mutation_lock():
        with pytest.raises(StoreLockTimeoutError):
            with store.mutation_lock():
                pytest.fail("second descriptor must not bypass the outer lock")
        with pytest.raises(StoreLockTimeoutError):
            with Store(tmp_path).mutation_lock(timeout_seconds=0):
                pytest.fail("timeout must leave the original lock held")
    with store.mutation_lock():
        pass


@pytest.mark.parametrize("timeout", [-1, float("inf"), float("nan")])
def test_invalid_timeout_rejected_before_entering_critical_section(tmp_path, timeout):
    with pytest.raises(ValueError, match="invalid_lock_timeout"):
        with Store(tmp_path).mutation_lock(timeout_seconds=timeout):
            pytest.fail("invalid timeout")


def test_kernel_owner_diagnostic_is_advisory(tmp_path):
    store = Store(tmp_path)
    with store.mutation_lock():
        with pytest.raises(StoreLockTimeoutError) as error:
            with store.mutation_lock(timeout_seconds=0):
                pass
        if os.path.exists("/proc/locks"):
            assert f"owner_pid={os.getpid()}" in str(error.value)


def test_api_initialization_and_ticket_update_preserve_store_on_timeout(tmp_path, monkeypatch):
    from planfile import Planfile

    pf = Planfile(tmp_path)
    ticket = pf.create_ticket(name="Preserve durable ticket")
    outbox = pf.store.base_dir / "sync" / "pending.json"
    outbox.parent.mkdir(exist_ok=True)
    outbox.write_text('{"pending": "preserve"}\n')
    pf.store._forensic_log_receipt_path.unlink()
    sprint = pf.store._sprint_file("current")
    original = sprint.read_bytes()
    monkeypatch.setattr(Store, "LOCK_TIMEOUT_SECONDS", 0.05)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    holder = context.Process(target=_hold_lock, args=(str(pf.store._lock_path), ready, release))
    holder.start()
    try:
        assert ready.wait(5)
        with pytest.raises(StoreLockTimeoutError):
            Planfile(tmp_path)
        with pytest.raises(StoreLockTimeoutError):
            pf.update_ticket(ticket.id, name="Must not overwrite")
        assert sprint.read_bytes() == original
        assert outbox.read_text() == '{"pending": "preserve"}\n'
    finally:
        release.set()
        holder.join(5)
        if holder.is_alive():
            holder.terminate()
            holder.join(5)
    resumed = Planfile(tmp_path)
    assert resumed.get_ticket(ticket.id).name == "Preserve durable ticket"
    resumed.update_ticket(ticket.id, name="Recovered writer")
    assert resumed.get_ticket(ticket.id).name == "Recovered writer"
    assert outbox.read_text() == '{"pending": "preserve"}\n'
