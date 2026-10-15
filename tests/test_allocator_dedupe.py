import json
import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier

import pytest

from planfile import Planfile
from planfile.core import allocator_dedupe as evidence
from planfile.core import allocator_sprints
from planfile.core.fastio import read_yaml_fast


def source(tmp_path):
    path = tmp_path / "archive.yaml"
    path.write_text("tickets:\n  PLF-900: {status: open, labels: ['dedupe:key']}\n")
    return path


def test_warm_evidence_does_not_decode_yaml(tmp_path, monkeypatch):
    path = source(tmp_path)
    expected = evidence.live_records(path)

    def unexpected(*a, **kw):
        pytest.fail("warm cache decoded source")

    monkeypatch.setattr(evidence, "load_yaml_text", unexpected)
    assert evidence.live_records(path, max_rebuild_bytes=1) == expected


@pytest.mark.parametrize("status", ["done", "canceled"])
def test_terminal_records_excluded_and_tasks_fallback_supported(tmp_path, status):
    path = source(tmp_path)
    path.write_text(f"tasks:\n  - status: {status}\n    labels: ['dedupe:closed']\n"
                    "  - labels: ['unrelated', 'dedupe:live']\n")
    assert evidence.live_records(path) == [{"id": "TSK-002", "created_at": "", "labels": ["dedupe:live"]}]


def test_stale_mirror_and_same_mtime_source_are_not_trusted(tmp_path):
    path = source(tmp_path)
    read_yaml_fast(path)  # Deliberately leave an old mtime-based mirror.
    assert evidence.live_records(path)[0]["id"] == "PLF-900"
    before = path.stat()
    replacement = path.with_suffix(".new")
    replacement.write_text(path.read_text().replace("PLF-900", "PLF-999"))
    os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
    replacement.replace(path)
    assert evidence.live_records(path)[0]["id"] == "PLF-999"


@pytest.mark.parametrize("corruption", ["checksum", "shape", "json"])
def test_corrupt_cache_is_rebuilt(tmp_path, corruption):
    path = source(tmp_path)
    expected = evidence.live_records(path)
    cache = next((tmp_path / "index/allocator-dedupe").glob("*.json"))
    value = json.loads(cache.read_text())
    if corruption == "json":
        cache.write_text("{broken")
    else:
        value["records"] = [] if corruption == "checksum" else [{"id": 900}]
        if corruption == "shape":
            value.pop("checksum")
            value["checksum"] = evidence._digest(value)
        cache.write_text(json.dumps(value))
    assert evidence.live_records(path) == expected


def test_changed_source_during_parse_fails_closed(tmp_path, monkeypatch):
    path = source(tmp_path)
    original = evidence.load_yaml_text

    def changed(text):
        path.write_text(text + "# changed\n")
        return original(text)

    monkeypatch.setattr(evidence, "load_yaml_text", changed)
    with pytest.raises(RuntimeError, match="Sprint changed"):
        evidence.live_records(path)
    assert not list((tmp_path / "index/allocator-dedupe").glob("*.json"))


def test_growth_after_stat_has_bounded_read(tmp_path, monkeypatch):
    path = source(tmp_path)
    bound = path.stat().st_size
    original = Path.open
    reads = []

    class GrowingSource:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            reads.append(size)
            return b"x" * size

    def opened(self, mode="r", *args, **kwargs):
        if self == path and mode == "rb":
            return GrowingSource()
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(RuntimeError, match="dedupe_evidence_changed_retry"):
        evidence.live_records(path, max_rebuild_bytes=bound)
    assert reads == [bound + 1]


def test_cache_write_failure_keeps_prepared_evidence_outside_lock(tmp_path, monkeypatch):
    pf = Planfile(tmp_path)
    existing = pf.create_ticket("first", dedupe_key="key")
    for cache in pf.store._sprints_dir.glob("index/allocator-dedupe/*.json"):
        cache.unlink()
    locked = False
    original_lock = pf.store.mutation_lock
    original_parse = evidence.load_yaml_text
    original_replace = os.replace

    @contextmanager
    def lock(**kwargs):
        nonlocal locked
        with original_lock(**kwargs):
            locked = True
            try:
                yield
            finally:
                locked = False

    def parse(text):
        assert not locked
        return original_parse(text)

    def replace(src, dst):
        if "allocator-dedupe" in str(dst):
            raise OSError("cache unavailable")
        return original_replace(src, dst)

    monkeypatch.setattr(pf.store, "mutation_lock", lock)
    monkeypatch.setattr(evidence, "load_yaml_text", parse)
    monkeypatch.setattr(os, "replace", replace)
    reused, created = pf.create_ticket_deduplicated("again", dedupe_key="key")
    assert reused.id == existing.id and not created


@pytest.mark.parametrize("added", [False, True])
def test_changed_large_source_at_lock_boundary_fails_closed(tmp_path, monkeypatch, added):
    pf = Planfile(tmp_path)
    pf.store.init()
    path = pf.store._sprint_file("archive")
    path.write_text("tickets: {}\n")
    original = pf.store.mutation_lock
    monkeypatch.setattr(allocator_sprints, "MAX_LOCKED_REBUILD_BYTES", 128)

    @contextmanager
    def lock(**kwargs):
        target = pf.store._sprint_file("added") if added else path
        target.write_text("tickets: {}\n#" + "x" * 129)
        with original(**kwargs):
            yield

    monkeypatch.setattr(pf.store, "mutation_lock", lock)
    with pytest.raises(RuntimeError, match="dedupe_evidence_changed_retry"):
        with pf.store.deduplication_lock("dedupe:key"):
            pytest.fail("stale evidence admitted")


def test_small_source_added_after_preparation_participates(tmp_path, monkeypatch):
    pf = Planfile(tmp_path)
    pf.store.init()
    original = pf.store.mutation_lock

    @contextmanager
    def lock(**kwargs):
        path = pf.store._sprint_file("added")
        path.write_text("tickets:\n  PLF-999: {labels: ['dedupe:key']}\n")
        with original(**kwargs):
            yield

    monkeypatch.setattr(pf.store, "mutation_lock", lock)
    with pf.store.deduplication_lock("dedupe:key") as live:
        assert [row["id"] for row in live] == ["PLF-999"]


@pytest.mark.parametrize("sharded", [False, True])
def test_reuse_oldest_and_occurrence_notes(tmp_path, sharded):
    pf = Planfile(tmp_path)
    older, newer = pf.create_tickets_bulk([
        {"name": "older", "labels": ["dedupe:key"], "created_at": "2025-01-01T00:00:00Z"},
        {"name": "newer", "labels": ["dedupe:key"], "created_at": "2025-02-01T00:00:00Z"},
    ])
    if sharded:
        pf.store.migrate_to_sharded_yaml()
    reused, created = pf.create_ticket_deduplicated("again", dedupe_key="key", dedupe_note="occurrence")
    assert not created and reused.id == older.id and reused.id != newer.id
    assert reused.outputs.notes[-1] == "occurrence"


def test_concurrent_creators_revalidate_after_preparation(tmp_path):
    Planfile(tmp_path).store.init()
    barrier = Barrier(2)

    def create():
        pf = Planfile(tmp_path)
        original = pf.store.mutation_lock

        @contextmanager
        def lock(**kwargs):
            barrier.wait(timeout=10)  # Both independent stores prepared the old snapshot.
            with original(**kwargs):
                yield

        pf.store.mutation_lock = lock
        ticket, created = pf.create_ticket_deduplicated("concurrent", dedupe_key="same")
        return ticket.id, created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert len({row[0] for row in results}) == 1
    assert sorted(row[1] for row in results) == [False, True]


def _process_create(path, barrier, results):
    pf = Planfile(path)
    original = pf.store.mutation_lock

    @contextmanager
    def lock(**kwargs):
        barrier.wait(timeout=30)
        with original(**kwargs):
            yield

    pf.store.mutation_lock = lock
    ticket, created = pf.create_ticket_deduplicated("process", dedupe_key="same")
    results.put((ticket.id, created))


def test_independent_processes_create_one_ticket(tmp_path):
    Planfile(tmp_path).store.init()
    context = multiprocessing.get_context("spawn")
    barrier, results = context.Barrier(2), context.Queue()
    processes = [context.Process(target=_process_create, args=(str(tmp_path), barrier, results))
                 for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=45)
            assert process.exitcode == 0
        rows = [results.get(timeout=5) for _ in processes]
        assert len({row[0] for row in rows}) == 1
        assert sorted(row[1] for row in rows) == [False, True]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        results.close()


def test_equal_timestamps_keep_original_record_order(tmp_path):
    pf = Planfile(tmp_path)
    first, _ = pf.create_tickets_bulk([
        {"name": name, "labels": ["dedupe:tie"], "created_at": "2025-01-01T00:00:00Z"}
        for name in ("first", "second")
    ])
    reused, created = pf.create_ticket_deduplicated("again", dedupe_key="tie")
    assert not created and reused.id == first.id


def test_without_key_does_not_prepare_dedupe_evidence(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("ordinary creation prepared dedupe evidence")

    monkeypatch.setattr(evidence, "live_records", unexpected)
    assert Planfile(tmp_path).create_ticket("ordinary").id == "PLF-001"


@pytest.mark.parametrize("large", [False, True])
def test_preparation_race_revalidated_under_lock(tmp_path, monkeypatch, large):
    pf = Planfile(tmp_path)
    pf.store.init()
    path = pf.store._sprint_file("archive")
    path.write_text("tickets: {}\n")
    original = evidence.load_yaml_text
    changed = False

    def parse(text):
        nonlocal changed
        if not changed and text == "tickets: {}\n":
            changed = True
            path.write_text("tickets:\n  PLF-900: {status: open, labels: ['dedupe:key']}\n"
                            + ("#" + "x" * 256 if large else ""))
        return original(text)

    monkeypatch.setattr(evidence, "load_yaml_text", parse)
    monkeypatch.setattr(allocator_sprints, "MAX_LOCKED_REBUILD_BYTES", 128)
    if large:
        with pytest.raises(RuntimeError, match="dedupe_evidence_changed_retry"):
            with pf.store.deduplication_lock("dedupe:key"):
                pytest.fail("large changed source admitted")
    else:
        with pf.store.deduplication_lock("dedupe:key") as rows:
            assert [row["id"] for row in rows] == ["PLF-900"]
    assert changed
