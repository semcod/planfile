import json
from pathlib import Path

import pytest

from planfile.core import allocator_sprints as evidence


def source_file(tmp_path, number=41):
    path = tmp_path / "archive.yaml"
    path.write_text(f"sprint:\n  tickets:\n    PLF-{number}: {{name: archived}}\n")
    return path


def test_cache_hit_does_not_parse_source(tmp_path, monkeypatch):
    path = source_file(tmp_path)
    assert evidence.sprint_highwater(path, "PLF") == 41

    def unexpected(*args, **kwargs):
        pytest.fail("warm evidence parsed YAML")

    monkeypatch.setattr(evidence, "load_yaml_text", unexpected)
    # A valid cache remains usable even when the source exceeds the cold bound.
    assert evidence.sprint_highwater(path, "PLF", max_rebuild_bytes=1) == 41


@pytest.mark.parametrize("replacement", [False, True])
def test_same_size_source_change_invalidates_cache(tmp_path, replacement):
    path = source_file(tmp_path)
    assert evidence.sprint_highwater(path, "PLF") == 41
    changed = path.with_suffix(".new") if replacement else path
    changed.write_text(path.read_text().replace("PLF-41", "PLF-99"))
    if replacement:
        changed.replace(path)
    assert evidence.sprint_highwater(path, "PLF") == 99


@pytest.mark.parametrize("corruption", ["json", "checksum", "shape"])
def test_invalid_cache_rebuilt(tmp_path, corruption):
    path = source_file(tmp_path)
    assert evidence.sprint_highwater(path, "PLF") == 41
    cache = next((tmp_path / "index/allocator-sprints").glob("*.json"))
    value = json.loads(cache.read_text())
    if corruption == "json":
        cache.write_text("{broken")
    else:
        value["highest"] = 0 if corruption == "checksum" else "41"
        cache.write_text(json.dumps(value))
    assert evidence.sprint_highwater(path, "PLF") == 41


def test_prefix_and_published_markers_are_reserved(tmp_path):
    path = source_file(tmp_path)
    path.write_text("""tickets:
  PLF-41:
    labels: ['published:PLF-75', 'other:ALT-90']
    description: 'PLF-80 then PLF-89'
  ALT-100: {}
""")
    assert evidence.sprint_highwater(path, "PLF") == 89
    assert evidence.sprint_highwater(path, "ALT") == 100
    assert evidence.sprint_highwater(path, "PLF") == 89


def test_task_fallback_identity(tmp_path):
    path = source_file(tmp_path)
    path.write_text("tasks:\n  - name: first\n  - name: second\n")
    assert evidence.sprint_highwater(path, "TSK") == 2


def test_oversized_cold_source_rejected_before_parse(tmp_path, monkeypatch):
    path = source_file(tmp_path)

    def unexpected(*args, **kwargs):
        pytest.fail("oversized source was parsed")

    monkeypatch.setattr(evidence, "load_yaml_text", unexpected)
    with pytest.raises(RuntimeError, match="allocator_evidence_changed_retry"):
        evidence.sprint_highwater(path, "PLF", max_rebuild_bytes=1)


def test_growth_after_stat_is_read_with_a_bound(tmp_path, monkeypatch):
    path = source_file(tmp_path)
    limit = path.stat().st_size
    original = Path.open
    reads = []

    class BoundedStream:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            reads.append(size)
            return b"x" * size

    def opened(self, mode="r", *args, **kwargs):
        if self == path and mode == "rb":
            return BoundedStream()
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(RuntimeError, match="allocator_evidence_changed_retry"):
        evidence.sprint_highwater(path, "PLF", max_rebuild_bytes=limit)
    assert reads == [limit + 1]


def test_source_change_during_parse_is_not_cached(tmp_path, monkeypatch):
    path = source_file(tmp_path)
    original = evidence.load_yaml_text

    def changed(text):
        path.write_text(text.replace("PLF-41", "PLF-99"))
        return original(text)

    monkeypatch.setattr(evidence, "load_yaml_text", changed)
    with pytest.raises(RuntimeError, match="Sprint changed"):
        evidence.sprint_highwater(path, "PLF")
    assert not list((tmp_path / "index/allocator-sprints").glob("*.json"))


def test_optional_cache_publication_failure_preserves_result(tmp_path, monkeypatch):
    path = source_file(tmp_path)

    def unavailable(*args, **kwargs):
        raise OSError("cache filesystem unavailable")

    monkeypatch.setattr(evidence.os, "replace", unavailable)
    assert evidence.sprint_highwater(path, "PLF") == 41
    assert not list((tmp_path / "index/allocator-sprints").iterdir())
