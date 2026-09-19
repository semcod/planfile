"""Executable demos must not write into their caller's real project queue."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from planfile import Planfile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "python-api"
SCRIPTS = sorted(path.name for path in EXAMPLES.glob("[0-9]*.py"))


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("script", [*SCRIPTS, "run_all.sh"])
def test_executable_demo_preserves_caller_project(tmp_path, script):
    project = tmp_path / "real-project"
    pf = Planfile(str(project))
    pf.create_ticket(name="Keep real work", priority="critical")
    nested = project / "nested"
    nested.mkdir()
    scratch = project / "temporary-directories"
    scratch.mkdir()
    before = snapshot(project)
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHON=sys.executable,
               PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(scratch))
    command = ["bash" if script.endswith(".sh") else sys.executable, str(EXAMPLES / script)]
    result = subprocess.run(command, cwd=nested, env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Disposable demo store:" in result.stdout
    assert snapshot(project) == before
    assert list(scratch.iterdir()) == []
    assert not (nested / ".planfile").exists()


def test_demo_failure_restores_cwd_and_removes_store(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("demo_store_under_test", EXAMPLES / "demo_store.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="demo failure"):
        with module.demo_store() as root:
            assert Path.cwd() == root
            with module.demo_store() as nested:
                assert nested == root
            Planfile.auto_discover().create_ticket(name="Temporary ticket")
            raise RuntimeError("demo failure")
    assert Path.cwd() == tmp_path
    assert not root.exists()
    assert not (tmp_path / ".planfile").exists()
    with module.demo_store() as second:
        assert second != root
        assert Planfile.auto_discover().list_tickets() == []


def test_logger_persists_error_warning_and_reraises(tmp_path, monkeypatch):
    from planfile.extensions import TicketLogger

    monkeypatch.chdir(tmp_path)
    logger = TicketLogger("example-test")
    error = logger.error("Example error", context={"operation": "demo"})
    warning = logger.warning("Example warning")
    assert error.name == "[example-test] Example error"
    assert warning.name == "[example-test] Example warning"
    assert logger.pf.get_ticket(error.id).source.context["operation"] == "demo"

    @logger.catch_errors
    def fail():
        raise ValueError("expected failure")

    with pytest.raises(ValueError, match="expected failure"):
        fail()
    assert len(logger.pf.list_tickets()) == 3
