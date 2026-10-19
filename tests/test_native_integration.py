"""planfile wiring of the optional planfile-native kernel (switch, fallback, parity)."""

from __future__ import annotations

import json
import warnings

import pytest
import yaml

from planfile.core import fastio, native
from planfile.core.models import Ticket
from planfile.core.store import Store

needs_native = pytest.mark.skipif(not native.available(), reason="planfile-native not installed")


def _store(tmp_path) -> Store:
    store = Store(tmp_path)
    store.init()
    return store


def _populate(store: Store) -> None:
    store.create_tickets_bulk(
        [
            Ticket(id=f"PLF-{i:03d}", name=f"Zażółć {i}: true", description="word " * 60 + f"\nline {i}")
            for i in range(25)
        ]
    )
    store.update_ticket("PLF-003", name="renamed 'quoted'")
    store.delete_ticket("PLF-004")


def test_mode_parsing_fails_closed(monkeypatch):
    monkeypatch.setenv(native.MODE_ENV, "bogus")
    assert native.mode() == "off" and not native.enabled()
    monkeypatch.setenv(native.MODE_ENV, " VERIFY ")
    assert native.mode() == "verify"
    monkeypatch.delenv(native.MODE_ENV)
    assert native.mode() == "auto"


@pytest.mark.parametrize("value,expected", [("1", True), ("0", False), ("off", False), ("No", False), ("yes", True)])
def test_fsync_switch(monkeypatch, value, expected):
    monkeypatch.setenv(native.FSYNC_ENV, value)
    assert native.fsync_enabled() is expected


def test_off_mode_never_calls_the_kernel(monkeypatch, tmp_path):
    monkeypatch.setenv(native.MODE_ENV, "off")
    assert native.dump_yaml({"a": 1}) is None
    assert native.normalize({"a": 1}) is None
    assert native.write_sprint(tmp_path / "x.yaml", {"a": 1}, allow_unicode=True, mirror_version=1, mirror_suffix=".m") is None
    assert not (tmp_path / "x.yaml").exists()


@needs_native
def test_native_written_sprint_files_are_pyyaml_fixed_points(monkeypatch, tmp_path):
    """Wall-clock event hashes make two runs differ, so check the invariant instead: re-dumping
    what the kernel wrote with PyYAML must reproduce the file byte for byte."""
    monkeypatch.setenv(native.MODE_ENV, "auto")
    _populate(_store(tmp_path))
    files = sorted((tmp_path / ".planfile" / "sprints").rglob("*.yaml"))
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert fastio.dump_yaml_python(yaml.safe_load(text), allow_unicode=True) == text, path.name


@needs_native
def test_native_write_leaves_a_valid_mirror_and_reads_back(monkeypatch, tmp_path):
    monkeypatch.setenv(native.MODE_ENV, "auto")
    store = _store(tmp_path)
    _populate(store)
    current = tmp_path / ".planfile" / "sprints" / "current.yaml"
    mirror = json.loads(fastio.mirror_path(current).read_text(encoding="utf-8"))
    assert mirror["version"] == fastio._MIRROR_VERSION
    assert mirror["yaml_mtime_ns"] == current.stat().st_mtime_ns
    assert fastio.read_mirror(current, current.stat().st_mtime_ns) == fastio.load_yaml_text(current.read_text(encoding="utf-8"))
    assert store.get_ticket("PLF-003").name == "renamed 'quoted'"
    assert store.get_ticket("PLF-004") is None


@needs_native
def test_unsupported_value_falls_back_to_pyyaml(monkeypatch, tmp_path):
    monkeypatch.setenv(native.MODE_ENV, "auto")
    shared = ["x"]
    data = {"a": shared, "b": shared}  # PyYAML emits an anchor; the kernel must refuse
    target = tmp_path / "shared.yaml"
    assert not fastio.write_sprint_native(target, data, allow_unicode=True)
    assert not target.exists()
    store = _store(tmp_path)
    store._write_yaml_atomic(target, data, allow_unicode=True)
    assert "&id001" in target.read_text(encoding="utf-8")


@needs_native
def test_verify_mode_accepts_matching_output_and_rejects_a_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv(native.MODE_ENV, "verify")
    assert fastio.dump_yaml({"k": "v"}) == "k: v\n"
    monkeypatch.setattr(fastio, "dump_yaml_python", lambda data, allow_unicode=False: "different\n")
    with pytest.raises(RuntimeError, match="differs from PyYAML"):
        native.dump_yaml({"k": "v"})


@needs_native
def test_mirror_write_failure_warns_without_raising(monkeypatch, tmp_path):
    monkeypatch.setenv(native.MODE_ENV, "auto")
    target = tmp_path / "current.yaml"
    fastio.mirror_path(target).mkdir()  # rename onto a directory fails
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert fastio.write_sprint_native(target, {"a": 1}, allow_unicode=True)
    assert target.read_text() == "a: 1\n"
    assert any("JSON mirror for current.yaml not written" in str(w.message) for w in caught)


@needs_native
def test_load_yaml_text_normalizes_temporal_values_identically(monkeypatch):
    text = "when: 2026-10-19 16:38:31\nday: 2026-10-19\nitems: [1, 2]\n"
    monkeypatch.setenv(native.MODE_ENV, "off")
    expected = fastio.load_yaml_text(text)
    monkeypatch.setenv(native.MODE_ENV, "auto")
    assert fastio.load_yaml_text(text) == expected == {
        "when": "2026-10-19T16:38:31",
        "day": "2026-10-19",
        "items": [1, 2],
    }
