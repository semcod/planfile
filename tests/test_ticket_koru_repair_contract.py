"""Repair inputs must survive the boundary before Koru executes them."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from planfile import Planfile, TicketInputs

REPAIR_INPUTS = {
    "provider": "opencode",
    "patch_mode": True,
    "promotion_mode": "branch",
    "worktree": True,
    "max_patch_attempts": 2,
    "verify_command": "python -m pytest tests/test_repair.py -q",
    "verify_profile": "python-pytest",
}


@pytest.mark.parametrize("sharded", [False, True])
def test_repair_contract_survives_store_update_and_cli(tmp_path, sharded):
    plan = Planfile(str(tmp_path))
    ticket = plan.create_ticket(
        "Repair a failed task",
        executor={"kind": "llm", "mode": "automatic"},
        inputs={"prompt": "Repair the declared files", **REPAIR_INPUTS},
    )
    if sharded:
        plan.store.migrate_to_sharded_yaml()
    plan.update_ticket(ticket.id, name="Repair the same failure")
    persisted = Planfile(str(tmp_path)).get_ticket(ticket.id).model_dump()["inputs"]
    assert {key: persisted.get(key) for key in REPAIR_INPUTS} == REPAIR_INPUTS
    result = subprocess.run(
        [sys.executable, "-m", "planfile.cli", "ticket", "show", ticket.id, "--format", "json"],
        cwd=tmp_path,
        env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    readback = json.loads(result.stdout)["inputs"]
    assert {key: readback.get(key) for key in REPAIR_INPUTS} == REPAIR_INPUTS


def test_api_partial_update_preserves_explicit_repair_contract(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from planfile import server_common
    from planfile.api import server

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(server_common, "_planfile", Planfile(str(tmp_path)))
    with TestClient(server.app) as client:
        created = client.post("/tickets", json={"name": "Repair task", "inputs": REPAIR_INPUTS})
        assert created.status_code in (200, 201), created.text
        ticket_id = created.json()["id"]
        updated = client.patch(
            f"/tickets/{ticket_id}",
            json={"actor": "test:agent", "reason": "Refine prompt", "inputs": {"prompt": "New prompt"}},
        )
        assert updated.status_code == 200, updated.text
        readback = client.get(f"/tickets/{ticket_id}").json()["inputs"]
        assert {key: readback.get(key) for key in REPAIR_INPUTS} == REPAIR_INPUTS


@pytest.mark.parametrize("exclude_none", [False, True])
def test_legacy_inputs_do_not_acquire_repair_defaults(exclude_none):
    inputs = TicketInputs(prompt="Explain an error")
    assert not REPAIR_INPUTS.keys() & inputs.model_dump(exclude_none=exclude_none).keys()
    assert not REPAIR_INPUTS.keys() & json.loads(inputs.model_dump_json()).keys()


@pytest.mark.parametrize("field", ["patch_mode", "worktree"])
@pytest.mark.parametrize("value", ["true", "false", 0, 1])
def test_repair_flags_do_not_coerce_strings_or_numbers(field, value):
    with pytest.raises(ValidationError):
        TicketInputs(**{field: value})


@pytest.mark.parametrize("value", [True, "2", -1])
def test_patch_attempts_are_nonnegative_integers(value):
    with pytest.raises(ValidationError):
        TicketInputs(max_patch_attempts=value)


@pytest.mark.parametrize("field", ["patch_mode", "worktree"])
@pytest.mark.parametrize("sharded", [False, True])
def test_explicit_disable_survives_roundtrip(tmp_path, field, sharded):
    plan = Planfile(str(tmp_path))
    ticket = plan.create_ticket("Keep repair disabled", inputs={field: False})
    if sharded:
        plan.store.migrate_to_sharded_yaml()
    inputs = Planfile(str(tmp_path)).get_ticket(ticket.id).inputs
    assert inputs.model_dump()[field] is False
    assert json.loads(inputs.model_dump_json())[field] is False
