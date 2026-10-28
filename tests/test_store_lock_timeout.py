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


def test_api_mutation_endpoints_return_typed_retryable_503_on_lock_contention_and_recover(
    tmp_path, monkeypatch
):
    from starlette.testclient import TestClient

    from planfile import Planfile
    from planfile.api import server as api_server

    pf = Planfile(tmp_path)
    ticket = pf.create_ticket(
        name="Contention protected ticket",
        execution={"attempt": 1, "max_attempts": 3, "assigned_to": "agent:owner"},
    )
    (tmp_path / "planfile.yaml").write_text("project: test\n", encoding="utf-8")
    sprint_file = pf.store._sprint_file("current")
    original_sprint_bytes = sprint_file.read_bytes()
    original_dump = ticket.model_dump(mode="json")

    monkeypatch.setattr(Store, "LOCK_TIMEOUT_SECONDS", 0.05)
    pf.store.LOCK_TIMEOUT_SECONDS = 0.05
    monkeypatch.setattr(api_server, "get_planfile", lambda: pf)

    lock_path = pf.store._lock_path
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    holder = context.Process(target=_hold_lock, args=(str(lock_path), ready, release))
    holder.start()
    try:
        assert ready.wait(5)
        inode = lock_path.stat().st_ino
        with TestClient(api_server.app, raise_server_exceptions=False) as client:
            assert "ticket.store_lock_timeout.retryable_503" in api_server.API_CAPABILITIES

            requests_to_check = [
                ("PATCH", f"/tickets/{ticket.id}", {"name": "Blocked patch"}),
                (
                    "POST",
                    f"/tickets/{ticket.id}/update-if-current",
                    {"name": "Blocked CAS", "expected_updated_at": original_dump["updated_at"]},
                ),
                ("POST", "/tickets", {"name": "Blocked create"}),
                ("POST", f"/tickets/{ticket.id}/claim", {"assigned_to": "agent:other"}),
                ("POST", f"/tickets/{ticket.id}/start", {"assigned_to": "agent:other"}),
                ("POST", f"/tickets/{ticket.id}/complete", {"note": "Blocked complete"}),
                ("POST", f"/tickets/{ticket.id}/fail", {"error": "Blocked fail"}),
                (
                    "POST",
                    f"/tickets/{ticket.id}/evidence",
                    {
                        "idempotency_key": "ev-busy-1",
                        "collection": "checks",
                        "evidence": {"status": "busy"},
                        "actor": "agent:test",
                        "reason": "contention check",
                    },
                ),
                (
                    "POST",
                    "/dsl",
                    {
                        "command": f"update ticket {ticket.id} status=in_progress",
                        "project_path": str(tmp_path),
                    },
                ),
                ("PATCH", "/yaml", {"path": "project", "value": "mutated"}),
            ]

            for method, path, payload in requests_to_check:
                started = time.monotonic()
                resp = client.request(method, path, json=payload)
                assert time.monotonic() - started < 2.0
                assert resp.status_code == 503, f"{method} {path} returned {resp.status_code}: {resp.text}"
                assert resp.headers.get("Retry-After") == "5"
                assert resp.headers.get("Cache-Control") == "no-store, max-age=0"
                body = resp.json()
                assert body == {
                    "detail": "ticket_store_lock_timeout",
                    "code": "ticket_store_lock_timeout",
                    "retryable": True,
                    "retry_after_seconds": 5,
                }
                # Ensure no host paths, lock filenames, or PIDs leak into the HTTP response
                raw_text = resp.text
                assert str(tmp_path) not in raw_text
                assert ".store.lock" not in raw_text
                assert "owner_pid=" not in raw_text

            # Verify writer ownership, lock inode, and ticket/store state are completely untouched
            assert holder.is_alive()
            assert lock_path.stat().st_ino == inode
            assert sprint_file.read_bytes() == original_sprint_bytes
            assert not pf.store._ticket_evidence_path(ticket.id).exists()
            current = pf.get_ticket(ticket.id, repair_index=False)
            assert current is not None
            assert current.model_dump(mode="json") == original_dump
            assert current.execution.attempt == 1
    finally:
        release.set()
        holder.join(5)
        if holder.is_alive():
            holder.terminate()
            holder.join(5)

    # After lock release, supported operations, CAS, and evidence idempotency work normally
    with TestClient(api_server.app, raise_server_exceptions=False) as client:
        # Stale CAS precondition still returns 409
        stale_cas = client.post(
            f"/tickets/{ticket.id}/update-if-current",
            json={"name": "Stale", "expected_updated_at": "1999-01-01T00:00:00+00:00"},
        )
        assert stale_cas.status_code == 409
        assert stale_cas.json()["detail"] == "ticket_updated_at_precondition_failed"

        # Valid PATCH succeeds
        ok_patch = client.patch(
            f"/tickets/{ticket.id}",
            json={"name": "Updated after release", "expected_updated_at": original_dump["updated_at"]},
        )
        assert ok_patch.status_code == 200
        assert ok_patch.json()["name"] == "Updated after release"

        # Evidence append and conflicting key check
        ev_payload = {
            "idempotency_key": "ev-busy-1",
            "collection": "checks",
            "evidence": {"status": "passed"},
            "actor": "agent:test",
            "reason": "post-release append",
        }
        ev1 = client.post(f"/tickets/{ticket.id}/evidence", json=ev_payload)
        assert ev1.status_code == 200
        assert ev1.json()["recorded"] is True

        ev_dup = client.post(f"/tickets/{ticket.id}/evidence", json=ev_payload)
        assert ev_dup.status_code == 200
        assert ev_dup.json()["deduplicated"] is True

        ev_conflict = client.post(
            f"/tickets/{ticket.id}/evidence",
            json={**ev_payload, "evidence": {"status": "different"}},
        )
        assert ev_conflict.status_code == 409

        # Unexpected internal error still surfaces as HTTP 500
        def _boom(*_args, **_kwargs):
            raise RuntimeError("unexpected_internal_failure")

        monkeypatch.setattr(pf, "update_ticket", _boom)
        err_resp = client.patch(f"/tickets/{ticket.id}", json={"name": "Boom"})
        assert err_resp.status_code == 500
