"""LLM context selectors must survive the same readback Koru executes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from planfile import Planfile, TicketInputs

CONTEXT_INPUTS = {
    "context_files": ["src/koru/tasks.py"],
    "context_globs": ["src/koru/task_*.py"],
    "include_project_context": False,
    "max_context_chars": 2048,
    "llm_timeout_seconds": 45.5,
}


@pytest.mark.parametrize("sharded", [False, True])
def test_context_survives_storage_and_cli_readback(tmp_path, sharded):
    plan = Planfile(str(tmp_path))
    ticket = plan.create_ticket(
        "Explain the actual source", inputs={"prompt": "Explain tasks.py", **CONTEXT_INPUTS}
    )
    if sharded:
        plan.store.migrate_to_sharded_yaml()
    plan.update_ticket(ticket.id, name="Unrelated title update")
    persisted = Planfile(str(tmp_path)).get_ticket(ticket.id).inputs.model_dump(exclude_none=True)
    assert {key: persisted.get(key) for key in CONTEXT_INPUTS} == CONTEXT_INPUTS
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [sys.executable, "-m", "planfile.cli", "ticket", "show", ticket.id, "--format", "json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    readback = json.loads(result.stdout)["inputs"]
    assert {key: readback.get(key) for key in CONTEXT_INPUTS} == CONTEXT_INPUTS


def test_legacy_prompt_does_not_acquire_context_or_timeout_defaults():
    inputs = TicketInputs(prompt="Legacy question")
    assert not CONTEXT_INPUTS.keys() & inputs.model_dump(exclude_none=True).keys()


def test_api_partial_prompt_update_retains_context(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from planfile import server_common
    from planfile.api import server

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(server_common, "_planfile", Planfile(str(tmp_path)))
    with TestClient(server.app) as client:
        created = client.post("/tickets", json={"name": "Explain source", "inputs": CONTEXT_INPUTS})
        assert created.status_code in (200, 201), created.text
        ticket_id = created.json()["id"]
        updated = client.patch(
            f"/tickets/{ticket_id}",
            json={
                "actor": "test:agent",
                "reason": "Refine question",
                "inputs": {"prompt": "Explain tasks.py"},
            },
        )
        assert updated.status_code == 200, updated.text
        readback = client.get(f"/tickets/{ticket_id}").json()["inputs"]
        assert {key: readback.get(key) for key in CONTEXT_INPUTS} == CONTEXT_INPUTS
