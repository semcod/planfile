from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def _cli(arguments: list[str], project: Path, **extra_env: str):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    for name in list(env):
        if name.endswith("_COMPLETE"):
            env.pop(name)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-B", "-m", "planfile", *arguments],
        cwd=project, env=env, capture_output=True, text=True, timeout=20,
    )


@pytest.mark.parametrize("completion", [False, True])
def test_ticket_entrypoint_loads_only_needed_groups(tmp_path, completion):
    script = """
import json, runpy, sys
sys.argv = ['planfile', 'ticket', '--help']
try:
    runpy.run_module('planfile', run_name='__main__')
except SystemExit as exc:
    assert exc.code in (0, None), exc.code
print('LOADED=' + json.dumps(sorted(sys.modules)))
"""
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    for name in list(env):
        if name.endswith("_COMPLETE"):
            env.pop(name)
    if completion:
        env["_OTHER_COMPLETE"] = "complete"
    result = subprocess.run(
        [sys.executable, "-B", "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    modules = json.loads(result.stdout.split("LOADED=", 1)[1])
    assert "planfile.cli.groups.ticket" in modules
    for group in ("auto", "generate", "serve", "query"):
        assert (f"planfile.cli.groups.{group}" in modules) is completion
    assert not (tmp_path / ".planfile").exists()


def test_ticket_entrypoint_preserves_real_lifecycle(tmp_path):
    created = _cli(["ticket", "create", "Startup regression"], tmp_path)
    assert created.returncode == 0, created.stderr
    from planfile.core.store import Store

    tickets = Store(tmp_path).list_tickets()
    assert len(tickets) == 1
    ticket_id = tickets[0].id
    shown = _cli(["ticket", "show", ticket_id, "--format", "json"], tmp_path)
    assert shown.returncode == 0, shown.stderr
    assert json.loads(shown.stdout)["name"] == "Startup regression"
    done = _cli(["ticket", "done", ticket_id], tmp_path)
    assert done.returncode == 0, done.stderr
    ticket = Store(tmp_path).get_ticket(ticket_id, repair_index=False)
    assert ticket.status.value == "done"
    assert len(Store(tmp_path).list_tickets(sprint="all")) == 1


def test_shell_completion_retains_all_root_commands(tmp_path):
    env = dict(
        os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1",
        _PLANFILE_COMPLETE="complete_bash", COMP_WORDS="planfile ", COMP_CWORD="1",
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c",
         "import sys; sys.argv=['planfile']; from planfile.cli.commands import main; main()"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    for command in ("ticket", "serve", "generate"):
        assert command in result.stdout.splitlines()
    assert not (tmp_path / ".planfile").exists()


@pytest.mark.parametrize("arguments", [
    [], ["--help"], ["--version"], ["auto", "loop", "--help"],
    ["shell", "help"], ["sh", "help"], ["ticket", "--help"],
    ["ticket", "unknown-command"], ["--unknown-option", "ticket"],
    ["--help", "ticket"],
])
def test_entrypoint_matches_public_app(arguments, tmp_path, monkeypatch):
    from planfile.cli.commands import app

    monkeypatch.chdir(tmp_path)
    direct = _cli(arguments, tmp_path)
    embedded = CliRunner().invoke(app, arguments)
    assert direct.returncode == embedded.exit_code
    # Rendering width and program name differ between entrypoints.
    for marker in ("ticket", "Usage:", "No such command", "No such option",
                   "version", "planfile DSL commands", "Run automated CI/CD loop"):
        assert (marker in direct.stdout + direct.stderr) == (marker in embedded.output)
    assert not (tmp_path / ".planfile").exists()
