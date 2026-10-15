from contextlib import contextmanager

import pytest

from planfile import Planfile
from planfile.core import allocator_sprints as evidence


def archive(store, number=900, name="archive"):
    path = store._sprint_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"sprint:\n  tickets:\n    PLF-{number}: {{name: archived}}\n")
    return path


def test_prepares_outside_lock_and_uses_scalar_when_cache_write_fails(tmp_path, monkeypatch):
    store = Planfile(tmp_path).store
    store.init()
    path = archive(store)
    locked = False
    parsed = []
    original_lock = store.mutation_lock
    original_parse = evidence.load_yaml_text

    @contextmanager
    def observed_lock(**kwargs):
        nonlocal locked
        with original_lock(**kwargs):
            locked = True
            try:
                yield
            finally:
                locked = False

    def parsed_outside(text):
        assert not locked, "cold YAML parse held mutation lock"
        parsed.append(text)
        return original_parse(text)

    def unavailable(*args, **kwargs):
        raise OSError("cache unavailable")

    monkeypatch.setattr(store, "mutation_lock", observed_lock)
    monkeypatch.setattr(evidence, "load_yaml_text", parsed_outside)
    monkeypatch.setattr(evidence.os, "replace", unavailable)
    with store.allocation_lock():
        assert locked
        assert (str(path), "PLF") in store._prepared_allocator_evidence
        assert store._known_ticket_highwater("PLF") == 900
    assert parsed
    assert store._prepared_allocator_evidence == {}


@pytest.mark.parametrize("added", [False, True])
def test_large_source_changed_at_lock_boundary_fails_closed(tmp_path, monkeypatch, added):
    store = Planfile(tmp_path).store
    store.init()
    path = archive(store)
    original = store.mutation_lock
    # Lower the bound to keep this deterministic without megabyte fixtures.
    monkeypatch.setattr(evidence, "MAX_LOCKED_REBUILD_BYTES", 100)

    @contextmanager
    def concurrent_change(**kwargs):
        target = archive(store, 999, "added") if added else path
        target.write_text(target.read_text() + "#" + "x" * 101)
        with original(**kwargs):
            yield

    monkeypatch.setattr(store, "mutation_lock", concurrent_change)
    before = store._read_config()
    with pytest.raises(RuntimeError, match="allocator_evidence_changed_retry"):
        store.next_id()
    assert store._read_config() == before
    assert store._prepared_allocator_evidence == {}


def test_small_source_changed_at_lock_boundary_is_rebuilt(tmp_path, monkeypatch):
    store = Planfile(tmp_path).store
    store.init()
    path = archive(store)
    original = store.mutation_lock

    @contextmanager
    def concurrent_change(**kwargs):
        path.write_text(path.read_text().replace("PLF-900", "PLF-999"))
        with original(**kwargs):
            yield

    monkeypatch.setattr(store, "mutation_lock", concurrent_change)
    assert store.next_id() == "PLF-1000"


def test_preparation_cleared_after_body_error(tmp_path):
    store = Planfile(tmp_path).store
    store.init()
    archive(store)
    with pytest.raises(ValueError, match="body failed"), store.allocation_lock():
        assert store._prepared_allocator_evidence
        raise ValueError("body failed")
    assert store._prepared_allocator_evidence == {}


def test_sharded_allocation_does_not_prepare_archive_yaml(tmp_path, monkeypatch):
    pf = Planfile(tmp_path)
    pf.create_ticket("existing")
    pf.store.migrate_to_sharded_yaml()

    def unexpected(*args, **kwargs):
        pytest.fail("sharded allocation used archive preparation")

    monkeypatch.setattr(evidence, "sprint_highwater", unexpected)
    assert pf.create_ticket("next").id == "PLF-002"
