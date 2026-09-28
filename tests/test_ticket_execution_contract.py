"""File-change expectations must reach the executor through native readback."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from planfile import Planfile, TicketInputs


@pytest.mark.parametrize("expected", [True, False])
def test_expectation_survives_storage_update_and_cli(tmp_path, expected):
    plan = Planfile(str(tmp_path))
    ticket = plan.create_ticket(
        "Verify declared output",
        inputs={"script": "true", "expect_files_changed": expected},
        files=["output.json"],
    )
    assert plan.get_ticket(ticket.id).inputs.model_dump()["expect_files_changed"] is expected
    plan.update_ticket(ticket.id, name="Unrelated title update")
    assert Planfile(str(tmp_path)).get_ticket(ticket.id).model_dump()["inputs"]["expect_files_changed"] is expected

    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [sys.executable, "-m", "planfile.cli", "ticket", "show", ticket.id, "--format", "json"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["inputs"]["expect_files_changed"] is expected


def test_omitted_expectation_does_not_override_label_inference(tmp_path):
    plan = Planfile(str(tmp_path))
    ticket = plan.create_ticket("Refactor", labels=["code-change"], inputs={"script": "true"})
    assert "expect_files_changed" not in TicketInputs(script="true").model_dump()
    assert "expect_files_changed" not in plan.get_ticket(ticket.id).model_dump()["inputs"]
    assert "expect_files_changed" not in json.loads(plan.get_ticket(ticket.id).model_dump_json())["inputs"]


@pytest.mark.parametrize("expected", [True, False])
def test_api_partial_inputs_update_keeps_expectation(tmp_path, monkeypatch, expected):
    from fastapi.testclient import TestClient

    from planfile import server_common
    from planfile.api import server

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(server_common, "_planfile", Planfile(str(tmp_path)))
    with TestClient(server.app) as client:
        created = client.post("/tickets", json={
            "name": "Verify output", "inputs": {"expect_files_changed": expected},
        })
        assert created.status_code in (200, 201), created.text
        ticket_id = created.json()["id"]
        patched = client.patch(f"/tickets/{ticket_id}", json={
            "actor": "test:agent", "reason": "unrelated prompt change",
            "inputs": {"prompt": "Updated prompt"},
        })
        assert patched.status_code == 200, patched.text
        assert client.get(f"/tickets/{ticket_id}").json()["inputs"]["expect_files_changed"] is expected


@pytest.mark.parametrize("invalid", ["true", "false", 0, 1, None])
def test_nonboolean_expectations_are_rejected(invalid):
    with pytest.raises(ValidationError):
        TicketInputs(expect_files_changed=invalid)
