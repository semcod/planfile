"""Tests for the sprint-YAML fast read layer (mirror + C loader)."""

from __future__ import annotations

import json

from planfile.core import fastio


def _write_yaml(path, text):
    path.write_text(text, encoding="utf-8")


class TestMirrorRoundtrip:
    def test_first_read_parses_and_heals_mirror(self, tmp_path):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "sprint:\n  tickets:\n    PLF-1:\n      name: a\n")
        data = fastio.read_yaml_fast(y)
        assert data["sprint"]["tickets"]["PLF-1"]["name"] == "a"
        assert fastio.mirror_path(y).exists()

    def test_second_read_uses_mirror(self, tmp_path, monkeypatch):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "sprint:\n  tickets: {}\n")
        fastio.read_yaml_fast(y)  # heal mirror

        def boom(_text):
            raise AssertionError("YAML must not be parsed when mirror is fresh")

        monkeypatch.setattr(fastio, "load_yaml_text", boom)
        data = fastio.read_yaml_fast(y)
        assert data == {"sprint": {"tickets": {}}}

    def test_external_yaml_edit_invalidates_mirror(self, tmp_path):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "sprint:\n  tickets: {}\n")
        fastio.read_yaml_fast(y)
        import os
        _write_yaml(y, "sprint:\n  tickets:\n    PLF-9:\n      name: new\n")
        os.utime(y, ns=(y.stat().st_atime_ns, y.stat().st_mtime_ns + 1_000_000))
        data = fastio.read_yaml_fast(y)
        assert "PLF-9" in data["sprint"]["tickets"]

    def test_corrupt_mirror_falls_back_to_yaml(self, tmp_path):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "sprint:\n  tickets: {}\n")
        fastio.mirror_path(y).write_text("{not json", encoding="utf-8")
        assert fastio.read_yaml_fast(y) == {"sprint": {"tickets": {}}}

    def test_missing_yaml_returns_none(self, tmp_path):
        assert fastio.read_yaml_fast(tmp_path / "nope.yaml") is None

    def test_write_mirror_records_current_mtime(self, tmp_path):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "a: 1\n")
        fastio.write_mirror(y, {"a": 1})
        payload = json.loads(fastio.mirror_path(y).read_text())
        assert payload["yaml_mtime_ns"] == y.stat().st_mtime_ns
        assert payload["data"] == {"a": 1}

    def test_write_mirror_uses_explicit_mtime_without_restat(self, tmp_path, monkeypatch):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "a: 1\n")

        def boom(_path):
            raise AssertionError("must not re-stat when the caller already provided mtime_ns")

        monkeypatch.setattr(fastio, "_stat_mtime_ns", boom)
        fastio.write_mirror(y, {"a": 1}, mtime_ns=12345)
        payload = json.loads(fastio.mirror_path(y).read_text())
        assert payload["yaml_mtime_ns"] == 12345

    def test_yaml_timestamps_are_json_safe_and_mirrored(self, tmp_path):
        y = tmp_path / "archive.yaml"
        _write_yaml(
            y,
            "created_at: 2026-08-05 07:11:31.523310+00:00\n"
            "review_on: 2026-08-12\n",
        )

        first = fastio.read_yaml_fast(y)

        assert first == {
            "created_at": "2026-08-05T07:11:31.523310+00:00",
            "review_on": "2026-08-12",
        }
        assert fastio.mirror_path(y).exists()
        assert fastio.read_yaml_fast(y) == first

    def test_read_does_not_cache_when_a_writer_races_mid_read(self, tmp_path, monkeypatch):
        """Reproduces the exact bug this module guards against: a reader takes no
        lock, so a concurrent writer's atomic replace can land between the reader's
        initial stat and its content read. Without the post-read mtime recheck, the
        reader would cache its (possibly stale/inconsistent) parse under whatever
        mtime a LATER independent stat happened to return — a mismatched pair every
        subsequent reader then trusts forever."""
        y = tmp_path / "current.yaml"
        _write_yaml(y, "sprint:\n  tickets:\n    PLF-1:\n      name: a\n")
        real_stat = fastio._stat_mtime_ns
        calls = {"n": 0}

        def racy_stat(path):
            calls["n"] += 1
            base = real_stat(path)
            return base + 1 if calls["n"] == 2 else base

        monkeypatch.setattr(fastio, "_stat_mtime_ns", racy_stat)
        data = fastio.read_yaml_fast(y)
        assert data["sprint"]["tickets"]["PLF-1"]["name"] == "a"
        assert not fastio.mirror_path(y).exists(), \
            "must not cache a read that raced a concurrent writer"


class TestMirrorAudit:
    def test_detects_and_heals_a_stale_mirror(self, tmp_path):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "sprint:\n  tickets:\n    PLF-1:\n      name: a\n")
        # The exact shape of the bug this guards against: a mirror stamped with the
        # file's CURRENT (correct) mtime but holding stale/empty data — as if an
        # earlier reader's snapshot got tagged with a later writer's mtime.
        bad_payload = {"version": 1, "yaml_mtime_ns": y.stat().st_mtime_ns, "data": {}}
        fastio.mirror_path(y).write_text(json.dumps(bad_payload), encoding="utf-8")

        result = fastio.audit_mirror(y)
        assert result["ok"] is False
        assert result["healed"] is True

        healed = json.loads(fastio.mirror_path(y).read_text())
        assert healed["data"]["sprint"]["tickets"]["PLF-1"]["name"] == "a"
        assert fastio.read_yaml_fast(y)["sprint"]["tickets"]["PLF-1"]["name"] == "a"

    def test_clean_mirror_reports_ok(self, tmp_path):
        y = tmp_path / "current.yaml"
        _write_yaml(y, "sprint:\n  tickets: {}\n")
        fastio.read_yaml_fast(y)  # creates a correct mirror
        assert fastio.audit_mirror(y) == {
            "path": str(y), "ok": True, "healed": False, "reason": None,
        }

    def test_project_audit_walks_every_yaml(self, tmp_path):
        base = tmp_path / ".planfile"
        (base / "sprints").mkdir(parents=True)
        y1 = base / "sprints" / "current.yaml"
        y2 = base / "config.yaml"
        _write_yaml(y1, "sprint:\n  tickets: {}\n")
        _write_yaml(y2, "project: x\n")
        fastio.read_yaml_fast(y1)
        fastio.read_yaml_fast(y2)

        results = fastio.audit_project_mirrors(base)
        assert {r["path"] for r in results} == {str(y1), str(y2)}
        assert all(r["ok"] for r in results)


class TestStoreIntegration:
    def test_update_ticket_refreshes_mirror(self, tmp_path):
        from planfile.core.store import Store

        store = Store(tmp_path)
        store.initialize() if hasattr(store, "initialize") else None
        from planfile.models import Ticket

        t = Ticket(id="PLF-001", name="test ticket")
        store.create_ticket(t)
        sprint_file = tmp_path / ".planfile" / "sprints" / "current.yaml"
        mirror = fastio.mirror_path(sprint_file)
        assert mirror.exists(), "create must write the mirror"
        first = mirror.read_text()
        store.update_ticket("PLF-001", status="done")
        assert mirror.read_text() != first, "update must refresh the mirror"
        got = store.get_ticket("PLF-001")
        assert str(getattr(got, "status", "")).endswith("done")
