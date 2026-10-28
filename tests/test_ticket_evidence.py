"""Opaque results and atomic evidence remain independent of index maintenance."""
import multiprocessing
import time
from contextlib import contextmanager

import pytest

from planfile import Planfile
from planfile.core.store import StoreLockTimeoutError


def _hold_evidence_lock(path, ready, release):
    import fcntl

    with open(path, "a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        ready.set()
        release.wait(20)


@contextmanager
def _live_evidence_lock(path):
    pytest.importorskip("fcntl")
    path.parent.mkdir(parents=True, exist_ok=True)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    holder = context.Process(target=_hold_evidence_lock, args=(str(path), ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        yield holder
    finally:
        release.set()
        holder.join(5)
        if holder.is_alive():
            holder.terminate()  # Only the child created by this fixture.
            holder.join(5)


@pytest.mark.parametrize('sharded', [False, True])
@pytest.mark.parametrize('result', ['deployed-and-verified', 23, [1, 2], False, None, {'status': 'ok'}])
def test_result_roundtrip_and_cas_update_without_evidence(tmp_path, sharded, result):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket('Valid opaque result', outputs={'result': result})
    if sharded:
        pf.store.migrate_to_sharded_yaml()
    for repair in [False, True]:
        found = pf.get_ticket(ticket.id, repair_index=repair)
        assert found is not None
        assert found.outputs.result == result
    located = pf.store._locate_ticket_source(ticket.id)
    source = pf.store._ticket_from_data(located[1])
    assert source is not None and source.outputs.result == result
    found = pf.get_ticket(ticket.id)
    updated = pf.update_ticket(ticket.id, expected_updated_at=found.updated_at.isoformat(), description='Guarded update')
    assert updated is not None and updated.outputs.result == result


def test_scalar_result_evidence_rejection_preserves_ticket(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket('Scalar result', outputs={'result': 'deployed-and-verified'})
    with pytest.raises(ValueError, match='ticket_output_result_not_object'):
        pf.append_ticket_evidence(ticket.id, idempotency_key='example-receipt', collection='checks',
                                  evidence={'status': 'passed'}, reason='Observed check', actor='test')
    assert pf.get_ticket(ticket.id).outputs.result == 'deployed-and-verified'


def test_object_result_accepts_idempotent_evidence(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket('Object result', outputs={'result': {'status': 'ok'}})
    args = {
        'idempotency_key': 'example-receipt', 'collection': 'checks',
        'evidence': {'status': 'passed'}, 'reason': 'Observed check', 'actor': 'test',
    }
    first, added = pf.append_ticket_evidence(ticket.id, **args)
    assert added and first.outputs.result['status'] == 'ok'
    repeated, added = pf.append_ticket_evidence(ticket.id, **args)
    assert not added and len(repeated.outputs.result['checks']) == 1


@pytest.mark.parametrize("sharded", [False, True])
def test_evidence_append_preserves_replay_with_live_index_rebuilder(tmp_path, sharded):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        "Preserve atomic evidence",
        inputs={"prompt": "Original task"},
        execution={"state": "ready", "attempt": 1, "max_attempts": 3},
        outputs={"result": {"preserved": "original"}, "notes": ["Existing note"]},
    )
    if sharded:
        pf.store.migrate_to_sharded_yaml()
    pf.store.configure_ticket_index(True)
    pf.store._sqlite_ticket_index().reset()
    pf.store.LOCK_TIMEOUT_SECONDS = 0.15
    before = ticket.model_dump(mode="json")
    args = {
        "idempotency_key": "fixture-index-busy",
        "collection": "checks",
        "evidence": {"status": "observed"},
        "reason": "Observed existing publication",
        "actor": "test",
    }
    lock = pf.store._ticket_index_rebuild_lock_path
    with _live_evidence_lock(lock) as holder:
        inode = lock.stat().st_ino
        first, recorded = pf.append_ticket_evidence(ticket.id, **args)
        assert recorded
        assert first is not None
        first_bytes = pf.store._ticket_evidence_path(ticket.id).read_bytes()
        repeated, recorded = pf.append_ticket_evidence(ticket.id, **args)
        assert not recorded
        assert repeated.updated_at == first.updated_at
        assert pf.store._ticket_evidence_path(ticket.id).read_bytes() == first_bytes
        with pytest.raises(ValueError, match="evidence_idempotency_conflict"):
            pf.append_ticket_evidence(ticket.id, **{**args, "evidence": {"status": "different"}})
        assert pf.store._ticket_evidence_path(ticket.id).read_bytes() == first_bytes
        current = pf.get_ticket(ticket.id, repair_index=False)
        assert current is not None
        for key in ("inputs", "execution", "status"):
            assert current.model_dump(mode="json")[key] == before[key]
        assert current.outputs.result["preserved"] == "original"
        assert current.outputs.result["checks"] == [
            {"status": "observed", "idempotency_key": "fixture-index-busy"}
        ]
        assert "Existing note" in current.outputs.notes
        assert holder.is_alive()
        assert lock.stat().st_ino == inode
    # Restart-style reads must recover the same journal while rebuilding the cache.
    restarted = Planfile(str(tmp_path)).get_ticket(ticket.id)
    assert restarted is not None
    assert restarted.model_dump(mode="json") == current.model_dump(mode="json")


def test_evidence_append_still_requires_the_real_mutation_lock(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket("Do not bypass writer ownership", outputs={"result": {"before": True}})
    pf.store.LOCK_TIMEOUT_SECONDS = 0.15
    lock = pf.store._lock_path
    with _live_evidence_lock(lock) as holder:
        inode = lock.stat().st_ino
        started = time.monotonic()
        with pytest.raises(StoreLockTimeoutError, match="planfile_store_lock_timeout"):
            pf.append_ticket_evidence(
                ticket.id, idempotency_key="fixture-writer-busy", collection="checks",
                evidence={"status": "unsafe"}, actor="test", reason="Must refuse",
            )
        assert time.monotonic() - started < 3
        assert not pf.store._ticket_evidence_path(ticket.id).exists()
        assert holder.is_alive()
        assert lock.stat().st_ino == inode
    current = pf.get_ticket(ticket.id)
    assert current is not None
    assert current.model_dump(mode="json") == ticket.model_dump(mode="json")
