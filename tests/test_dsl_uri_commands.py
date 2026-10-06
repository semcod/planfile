"""Tests for NL URI ticket commands, shared compiler adapter, exact URI validation,
ambiguity abstention, dry-run preflight, and wellmanifest.nl-plan/v1 envelope execution.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from planfile import Planfile
from planfile.dsl.executor import DSLExecutor
from planfile.dsl.parser import DSLParser


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary initialized planfile project."""
    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="Initial Ticket", priority="normal")
    return tmp_path


# ── 1. URI Parser Direct Patterns ─────────────────────────────────────────────


def test_parse_uri_create_ticket_json():
    parser = DSLParser()
    cmd = parser.parse('planfile://tickets/command/create {"name": "Fix auth leak", "priority": "high"}')
    assert cmd.verb == "create"
    assert cmd.object_type == "ticket"
    assert cmd.params.get("name") == "Fix auth leak"
    assert cmd.params.get("priority") == "high"
    assert cmd.target == "Fix auth leak"


def test_parse_uri_create_ticket_with_uri_prefix_and_title():
    parser = DSLParser()
    cmd = parser.parse('uri: planfile://tickets/command/create {"title": "Fix UI glitch", "priority": "low"}')
    assert cmd.verb == "create"
    assert cmd.object_type == "ticket"
    assert cmd.params.get("title") == "Fix UI glitch"
    assert cmd.params.get("name") == "Fix UI glitch"
    assert cmd.target == "Fix UI glitch"


def test_parse_uri_create_ticket_kv_args():
    parser = DSLParser()
    cmd = parser.parse('planfile://tickets/command/create name="Quick Task" priority=critical')
    assert cmd.verb == "create"
    assert cmd.object_type == "ticket"
    assert cmd.params.get("name") == "Quick Task"
    assert cmd.params.get("priority") == "critical"


def test_parse_uri_ticket_action_commands():
    parser = DSLParser()

    cmd_done = parser.parse("planfile://tickets/PLF-101/command/done")
    assert cmd_done.verb == "done"
    assert cmd_done.object_type == "ticket"
    assert cmd_done.target == "PLF-101"

    cmd_close = parser.parse("uri: planfile://tickets/PLF-101/command/close")
    assert cmd_close.verb == "done"
    assert cmd_close.target == "PLF-101"

    cmd_start = parser.parse("planfile://tickets/PLF-101/command/start")
    assert cmd_start.verb == "start"
    assert cmd_start.target == "PLF-101"

    cmd_block = parser.parse('planfile://tickets/PLF-101/command/block {"reason": "Waiting for review"}')
    assert cmd_block.verb == "block"
    assert cmd_block.target == "PLF-101"
    assert cmd_block.params.get("reason") == "Waiting for review"

    cmd_update = parser.parse('planfile://tickets/PLF-101/command/update {"priority": "critical"}')
    assert cmd_update.verb == "update"
    assert cmd_update.target == "PLF-101"
    assert cmd_update.params.get("priority") == "critical"

    cmd_del = parser.parse("planfile://tickets/PLF-101/command/delete")
    assert cmd_del.verb == "delete"
    assert cmd_del.target == "PLF-101"

    cmd_move = parser.parse('planfile://tickets/PLF-101/command/move {"to": "sprint-2"}')
    assert cmd_move.verb == "move"
    assert cmd_move.target == "PLF-101"
    assert cmd_move.params.get("to") == "sprint-2"


def test_parse_uri_query_and_config_commands():
    parser = DSLParser()

    cmd_show_ticket = parser.parse("planfile://tickets/PLF-101")
    assert cmd_show_ticket.verb == "show"
    assert cmd_show_ticket.object_type == "ticket"
    assert cmd_show_ticket.target == "PLF-101"

    cmd_list_tickets = parser.parse('planfile://tickets {"sprint": "current", "status": "todo"}')
    assert cmd_list_tickets.verb == "list"
    assert cmd_list_tickets.object_type == "ticket"
    assert cmd_list_tickets.params.get("status") == "todo"

    cmd_sprint_tickets = parser.parse("planfile://sprints/current/tickets")
    assert cmd_sprint_tickets.verb == "list"
    assert cmd_sprint_tickets.object_type == "ticket"
    assert cmd_sprint_tickets.params.get("sprint") == "current"

    cmd_sync = parser.parse('planfile://sync {"integration": "github"}')
    assert cmd_sync.verb == "sync"
    assert cmd_sync.params.get("integration") == "github"

    cmd_cfg = parser.parse("planfile://config")
    assert cmd_cfg.verb == "show"
    assert cmd_cfg.object_type == "config"

    cmd_cfg_path = parser.parse("planfile://config/store.archive.enabled")
    assert cmd_cfg_path.verb == "show"
    assert cmd_cfg_path.object_type == "config"
    assert cmd_cfg_path.target == "store.archive.enabled"

    cmd_cfg_set = parser.parse('planfile://config/command/set {"store.archive.enabled": false}')
    assert cmd_cfg_set.verb == "update"
    assert cmd_cfg_set.object_type == "config"
    assert cmd_cfg_set.params.get("store.archive.enabled") is False


# ── 2. Exact Validation & Ambiguity Abstention ─────────────────────────────────


def test_uri_exact_validation_abstention():
    parser = DSLParser()

    # Empty URI path
    cmd_empty = parser.parse("planfile://")
    assert cmd_empty.verb == "unknown"
    assert "Empty planfile URI path" in cmd_empty.params.get("error", "")

    # Unrecognized path
    cmd_unrec = parser.parse("planfile://unsupported/endpoint")
    assert cmd_unrec.verb == "unknown"
    assert "Invalid or unrecognized planfile URI path" in cmd_unrec.params.get("error", "")

    # Unrecognized action on ticket
    cmd_bad_action = parser.parse("planfile://tickets/PLF-1/command/fly_to_moon")
    assert cmd_bad_action.verb == "unknown"
    assert "Unrecognized ticket action 'fly_to_moon'" in cmd_bad_action.params.get("error", "")

    # Query strings and fragments must be rejected per SEMANTIC_NL_PLAN
    cmd_query = parser.parse("planfile://tickets?status=open")
    assert cmd_query.verb == "unknown"
    assert "Query strings and fragments are excluded" in cmd_query.params.get("error", "")

    cmd_fragment = parser.parse("planfile://tickets#details")
    assert cmd_fragment.verb == "unknown"
    assert "Query strings and fragments are excluded" in cmd_fragment.params.get("error", "")

    # Malformed JSON in arguments
    cmd_bad_json = parser.parse("planfile://tickets/command/create {invalid:json}")
    assert cmd_bad_json.verb == "unknown"
    assert "Malformed JSON arguments" in cmd_bad_json.params.get("error", "")

    # JSON not an object
    cmd_json_array = parser.parse("planfile://tickets/command/create [1, 2, 3]")
    assert cmd_json_array.verb == "unknown"
    assert "JSON arguments must be an object" in cmd_json_array.params.get("error", "")


def test_executor_abstains_on_rejected_uri(temp_project: Path):
    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    res = executor.run("planfile://nonexistent/command")
    assert not res.ok
    assert "Invalid or unrecognized planfile URI path" in (res.error or "")


# ── 3. Execution & Authoritative Allocator ─────────────────────────────────────


def test_executor_create_ticket_authoritative_allocator(temp_project: Path):
    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    res = executor.run('planfile://tickets/command/create {"title": "Real Ticket", "priority": "high"}')
    assert res.ok
    assert res.data is not None
    ticket_id = res.data["id"]
    assert ticket_id  # Assigned authoritatively by store allocator
    assert res.data["name"] == "Real Ticket"
    assert res.data["priority"] == "high"

    # Verify readback from planfile
    pf = Planfile(str(temp_project))
    stored = pf.get_ticket(ticket_id)
    assert stored is not None
    assert stored.name == "Real Ticket"


# ── 4. Dry-Run Preflight ──────────────────────────────────────────────────────


def test_executor_dry_run_create(temp_project: Path):
    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    res = executor.run(
        'planfile://tickets/command/create {"title": "Preview Only Ticket", "priority": "high"}',
        dry_run=True,
    )
    assert res.ok
    assert res.data.get("dry_run") is True
    preview_ticket = res.data.get("ticket")
    assert preview_ticket is not None
    preview_id = preview_ticket["id"]
    assert preview_id

    # Verify that the ticket was NOT created on disk
    pf = Planfile(str(temp_project))
    assert pf.get_ticket(preview_id) is None


def test_executor_dry_run_mutations(temp_project: Path):
    pf = Planfile(str(temp_project))
    initial = pf.list_tickets()[0]
    t_id = initial.id

    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)

    # Dry-run update
    res_up = executor.run(f'planfile://tickets/{t_id}/command/update {{"priority": "critical"}}', dry_run=True)
    assert res_up.ok
    assert isinstance(res_up.data, dict)
    assert res_up.data.get("dry_run") is True

    # Dry-run done
    res_done = executor.run(f"planfile://tickets/{t_id}/command/done", dry_run=True)
    assert res_done.ok
    assert isinstance(res_done.data, dict)
    assert res_done.data.get("dry_run") is True

    # Dry-run start
    res_start = executor.run(f"planfile://tickets/{t_id}/command/start", dry_run=True)
    assert res_start.ok
    assert isinstance(res_start.data, dict)
    assert res_start.data.get("dry_run") is True

    # Dry-run block
    res_block = executor.run(f'planfile://tickets/{t_id}/command/block {{"reason": "Test block"}}', dry_run=True)
    assert res_block.ok
    assert isinstance(res_block.data, dict)
    assert res_block.data.get("dry_run") is True

    # Verify original ticket state is completely UNCHANGED
    ticket = pf.get_ticket(t_id)
    assert ticket.status == initial.status
    assert ticket.priority == initial.priority

    # Dry-run on missing ticket fails
    res_missing = executor.run("planfile://tickets/NONEXISTENT-999/command/done", dry_run=True)
    assert not res_missing.ok
    assert "not found" in (res_missing.error or "")


# ── 5. wellmanifest.nl-plan/v1 Envelope Adapter ───────────────────────────────


def test_nl_plan_clarify(temp_project: Path):
    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    envelope = {
        "schema": "wellmanifest.nl-plan/v1",
        "status": "clarify",
        "question": "Which ticket would you like to close?",
    }
    res = executor.execute_plan(envelope)
    assert not res.ok
    assert res.source_layer == "nl_plan_v1"
    assert res.data.get("status") == "clarify"
    assert res.message == "Which ticket would you like to close?"


def test_nl_plan_unsupported(temp_project: Path):
    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    envelope = {
        "schema": "wellmanifest.nl-plan/v1",
        "status": "unsupported",
        "reason": "Conditional branching loops are unsupported in v1.",
    }
    res = executor.execute_plan(envelope)
    assert not res.ok
    assert res.source_layer == "nl_plan_v1"
    assert res.data.get("status") == "unsupported"
    assert "Conditional branching loops" in (res.error or "")


def test_nl_plan_call_execution(temp_project: Path):
    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    envelope = {
        "schema": "wellmanifest.nl-plan/v1",
        "status": "ok",
        "plan": {
            "kind": "call",
            "operation": "planfile://tickets/command/create",
            "arguments": {
                "title": "Created via nl-plan envelope",
                "priority": "normal",
            },
        },
    }
    res = executor.run(json.dumps(envelope))
    assert res.ok
    assert res.source_layer == "nl_plan_v1"
    assert res.data["name"] == "Created via nl-plan envelope"


def test_nl_plan_sequence_execution(temp_project: Path):
    pf = Planfile(str(temp_project))
    initial = pf.list_tickets()[0]
    t_id = initial.id

    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    envelope = {
        "schema": "wellmanifest.nl-plan/v1",
        "status": "ok",
        "plan": {
            "kind": "sequence",
            "calls": [
                {
                    "kind": "call",
                    "operation": f"planfile://tickets/{t_id}/command/start",
                    "arguments": {},
                },
                {
                    "kind": "call",
                    "operation": f"planfile://tickets/{t_id}/command/done",
                    "arguments": {},
                },
            ],
        },
    }
    res = executor.execute_plan(envelope)
    assert res.ok
    assert res.source_layer == "nl_plan_v1"
    assert res.data.get("steps_count") == 2
    assert len(res.data.get("step_results", [])) == 2

    ticket = pf.get_ticket(t_id)
    assert ticket.status == "done"


def test_nl_plan_sequence_bounds_rejection(temp_project: Path):
    executor = DSLExecutor(project_path=str(temp_project), discover_project=False)
    # Sequence with 0 calls is rejected
    env_empty = {
        "schema": "wellmanifest.nl-plan/v1",
        "status": "ok",
        "plan": {"kind": "sequence", "calls": []},
    }
    res = executor.execute_plan(env_empty)
    assert not res.ok
    assert "Sequence must contain 1-16 calls" in (res.error or "")

    # Sequence with 17 calls is rejected
    env_oversize = {
        "schema": "wellmanifest.nl-plan/v1",
        "status": "ok",
        "plan": {
            "kind": "sequence",
            "calls": [{"kind": "call", "operation": "planfile://tickets", "arguments": {}}] * 17,
        },
    }
    res_over = executor.execute_plan(env_oversize)
    assert not res_over.ok
    assert "Sequence must contain 1-16 calls" in (res_over.error or "")
