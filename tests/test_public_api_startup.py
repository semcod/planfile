"""Fresh-process import boundaries for the public Planfile API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TESTQL_EXPORTS = (
    "run_testql_validation",
    "build_testql_tickets",
    "upsert_testql_tickets",
    "sync_testql_tickets",
)


def _probe(tmp_path: Path, code: str) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PACKAGE_ROOT)
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("use_client", [False, True])
def test_ticket_api_does_not_import_testql(tmp_path: Path, use_client: bool) -> None:
    result = _probe(
        tmp_path,
        f"""
import json, sys
from planfile import Planfile
from planfile.client import PlanfileClient
backend = Planfile('.')
ticket = backend.create_ticket(name='Isolated startup lifecycle')
if {use_client!r}:
    client = PlanfileClient('.')
    assert client.claim(ticket.id, assigned_to='test').code == 'ok'
    assert client.start(ticket.id, assigned_to='test').code == 'ok'
    assert client.complete(ticket.id).code == 'ok'
else:
    backend.start_ticket(ticket.id)
    backend.complete_ticket(ticket.id)
assert backend.get_ticket(ticket.id).status.value == 'done'
print(json.dumps({{
    'testql_loaded': 'planfile.testql_integration' in sys.modules,
    'integration_config_loaded': 'planfile.integrations.config' in sys.modules,
}}))
""",
    )
    assert result == {"testql_loaded": False, "integration_config_loaded": False}


@pytest.mark.parametrize("name", TESTQL_EXPORTS)
def test_lazy_export_preserves_original_function(tmp_path: Path, name: str) -> None:
    result = _probe(
        tmp_path,
        f"""
import inspect, json, sys
import planfile
assert 'planfile.testql_integration' not in sys.modules
assert {name!r} in dir(planfile) and {name!r} in planfile.__all__
assert 'planfile.testql_integration' not in sys.modules
from planfile import {name} as exported
from planfile import testql_integration
original = getattr(testql_integration, {name!r})
assert exported is original
assert planfile.__dict__[{name!r}] is original
assert inspect.signature(exported) == inspect.signature(original)
print(json.dumps({{'module': exported.__module__, 'name': exported.__name__}}))
""",
    )
    assert result == {"module": "planfile.testql_integration", "name": name}


def test_unknown_attribute_does_not_load_testql(tmp_path: Path) -> None:
    result = _probe(
        tmp_path,
        """
import json, sys
import planfile
try:
    planfile.nonexistent_public_attribute
except AttributeError as error:
    message = str(error)
else:
    raise AssertionError('unknown attribute did not raise')
print(json.dumps({
    'message': message,
    'testql_loaded': 'planfile.testql_integration' in sys.modules,
}))
""",
    )
    assert result["message"] == "module 'planfile' has no attribute 'nonexistent_public_attribute'"
    assert result["testql_loaded"] is False


def test_lazy_ticket_builder_keeps_real_behavior(tmp_path: Path) -> None:
    result = _probe(
        tmp_path,
        """
import json
from planfile import build_testql_tickets
tickets = build_testql_tickets(
    {'ok': False, 'failed': 1, 'errors': ['GET /health expected 200 got 500']},
    'tests/health.testql.yaml',
)
print(json.dumps({'count': len(tickets), 'action': tickets[0]['action']}))
""",
    )
    assert result == {"count": 1, "action": "fix"}
