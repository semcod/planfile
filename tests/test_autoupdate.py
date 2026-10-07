from __future__ import annotations

import json
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import pytest

from planfile import autoupdate


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("NO_AUTOUPDATE", raising=False)
    monkeypatch.delenv("AUTO_UPGRADE", raising=False)
    monkeypatch.delenv("PLANFILE_AUTO_UPGRADE", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(autoupdate.metadata, "version", lambda _: "1.0")
    return tmp_path / "planfile"


def test_cold_cache_burst_launches_one_check(cache, monkeypatch):
    spawn = Mock()
    monkeypatch.setattr(autoupdate, "_spawn_detached_check", spawn)
    for _ in range(20):
        autoupdate.check_for_updates("planfile")
    assert spawn.call_count == 1
    assert not (cache / "update_check.json").exists()


def test_reservation_is_shared_and_nonblocking(cache):
    cache.mkdir()
    with ThreadPoolExecutor(max_workers=10) as pool:
        accepted = list(pool.map(lambda _: autoupdate._reserve_attempt(cache, "check", 60), range(20)))
    assert sum(accepted) == 1


def test_failed_launch_is_cooled_down_then_retried(cache, monkeypatch):
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(autoupdate.time, "time", clock)
    with patch.object(autoupdate.subprocess, "Popen", side_effect=OSError) as spawn:
        autoupdate.check_for_updates("planfile")
        autoupdate.check_for_updates("planfile")
        assert spawn.call_count == 1
        clock.return_value = 161.0
        autoupdate.check_for_updates("planfile")
        assert spawn.call_count == 2


@pytest.mark.parametrize("flag", ["CI", "NO_AUTOUPDATE"])
def test_disabled_checker_has_no_cache_or_process_effect(cache, monkeypatch, flag):
    monkeypatch.setenv(flag, "1")
    with patch.object(autoupdate.subprocess, "Popen") as spawn:
        autoupdate.check_for_updates("planfile")
        spawn.assert_not_called()
    assert not cache.exists()


@pytest.mark.parametrize("value", ["{", "[]", '{"last_check":"bad","latest_version":[]}'])
def test_malformed_cache_is_coalesced(cache, monkeypatch, value):
    cache.mkdir()
    (cache / "update_check.json").write_text(value)
    spawn = Mock()
    monkeypatch.setattr(autoupdate, "_spawn_detached_check", spawn)
    for _ in range(3):
        autoupdate.check_for_updates("planfile")
    assert spawn.call_count == 1


def test_fresh_cache_does_not_query(cache, monkeypatch):
    cache.mkdir()
    (cache / "update_check.json").write_text(json.dumps({"last_check": autoupdate.time.time(), "latest_version": "1.0"}))
    with patch.object(autoupdate.subprocess, "Popen") as spawn:
        autoupdate.check_for_updates("planfile")
        spawn.assert_not_called()


def test_upgrade_requires_opt_in_and_is_coalesced(cache, monkeypatch, capsys):
    cache.mkdir()
    (cache / "update_check.json").write_text(json.dumps({"last_check": autoupdate.time.time(), "latest_version": "2.0"}))
    upgrade = Mock()
    monkeypatch.setattr(autoupdate, "_spawn_background_upgrade", upgrade)
    autoupdate.check_for_updates("planfile")
    upgrade.assert_not_called()
    assert "pip install --upgrade planfile" in capsys.readouterr().err
    monkeypatch.setenv("PLANFILE_AUTO_UPGRADE", "1")
    for _ in range(20):
        autoupdate.check_for_updates("planfile")
    upgrade.assert_called_once_with("planfile")
    assert capsys.readouterr().err.count("Automatyczna aktualizacja") == 1


def test_unwritable_cache_and_busy_database_skip_quietly(cache, monkeypatch):
    with patch.object(autoupdate, "_get_cache_dir", side_effect=PermissionError), patch.object(autoupdate.subprocess, "Popen") as spawn:
        autoupdate.check_for_updates("planfile")
        spawn.assert_not_called()
    cache.mkdir()
    with sqlite3.connect(cache / "update_dispatch.sqlite", timeout=0) as lock:
        lock.execute("CREATE TABLE attempts (operation TEXT PRIMARY KEY, at REAL)")
        lock.execute("BEGIN IMMEDIATE")
        with patch.object(autoupdate.subprocess, "Popen") as spawn:
            autoupdate.check_for_updates("planfile")
            spawn.assert_not_called()


def test_corrupt_dispatch_database_skips_quietly(cache):
    cache.mkdir()
    (cache / "update_dispatch.sqlite").write_bytes(b"invalid database")
    with patch.object(autoupdate.subprocess, "Popen") as spawn:
        autoupdate.check_for_updates("planfile")
        spawn.assert_not_called()


def test_upgrade_child_has_a_timeout_and_propagates_failure():
    with patch.object(autoupdate.subprocess, "Popen") as spawn:
        autoupdate._spawn_background_upgrade("planfile")
    script = spawn.call_args.args[0][2]
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip", 300)) as run:
        with pytest.raises(SystemExit) as exit_:
            exec(script, {})
    assert exit_.value.code == 1
    assert run.call_args.kwargs == {"check": True, "timeout": 300}


def test_check_worker_atomically_publishes_cache(cache):
    cache.mkdir()
    path = cache / "update_check.json"
    response = Mock(status=200)
    response.read.return_value = b'{"info":{"version":"2.0"}}'
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    with patch.object(autoupdate.subprocess, "Popen") as spawn:
        autoupdate._spawn_detached_check("planfile", "1.0", path)
    script = spawn.call_args.args[0][2]
    with patch("urllib.request.urlopen", return_value=context):
        exec(script, {})
    assert json.loads(path.read_text())["latest_version"] == "2.0"
    assert not list(cache.glob(".update-check-*.json"))
