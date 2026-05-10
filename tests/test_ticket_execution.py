"""Tests for queue-oriented ticket execution metadata."""

from __future__ import annotations

from planfile import (
    Planfile,
    TicketExecution,
    TicketExecutor,
    TicketInputs,
    TicketOutputs,
    TicketSource,
)


def test_ticket_round_trip_with_execution_fields(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Bootstrap OpenRouter integration",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/bootstrap.sh"),
        execution=TicketExecution(state="pending", max_attempts=3),
        inputs=TicketInputs(env_keys=["OPENROUTER_API_KEY"], script="scripts/bootstrap.sh"),
        outputs=TicketOutputs(artifacts=["report.json"]),
    )

    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.executor is not None
    assert loaded.executor.kind == "shell"
    assert loaded.executor.handler == "scripts/bootstrap.sh"
    assert loaded.execution is not None
    assert loaded.execution.state == "pending"
    assert loaded.execution.max_attempts == 3
    assert loaded.inputs is not None
    assert loaded.inputs.env_keys == ["OPENROUTER_API_KEY"]
    assert loaded.outputs is not None
    assert loaded.outputs.artifacts == ["report.json"]


def test_next_ticket_respects_dependencies_execution_state_and_priority(tmp_path):
    pf = Planfile(str(tmp_path))

    blocked = pf.create_ticket(
        name="Provide API key",
        priority="normal",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive"),
        execution=TicketExecution(state="waiting_input"),
    )

    pf.create_ticket(
        name="Run bootstrap shell",
        priority="critical",
        blocked_by=[blocked.id],
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/bootstrap.sh"),
        execution=TicketExecution(state="pending"),
    )

    runnable = pf.create_ticket(
        name="Generate pyqual config",
        priority="high",
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/generate.sh"),
        execution=TicketExecution(state="ready"),
    )

    next_ticket = pf.next_ticket()
    assert next_ticket is not None
    assert next_ticket.id == runnable.id


def test_next_ticket_can_filter_by_execution_queue(tmp_path):
    pf = Planfile(str(tmp_path))

    default_ticket = pf.create_ticket(
        name="Default queue task",
        priority="critical",
        execution=TicketExecution(queue="default", state="ready"),
    )
    refactor_ticket = pf.create_ticket(
        name="Refactor queue task",
        priority="high",
        execution=TicketExecution(queue="c2004-refactor", state="ready"),
    )

    assert pf.next_ticket().id == default_ticket.id
    filtered = pf.next_ticket(queue="c2004-refactor")
    assert filtered is not None
    assert filtered.id == refactor_ticket.id


def test_next_ticket_unblocks_when_dependency_is_done(tmp_path):
    pf = Planfile(str(tmp_path))

    prerequisite = pf.create_ticket(
        name="Provide API key",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive"),
        execution=TicketExecution(state="waiting_input"),
    )
    dependent = pf.create_ticket(
        name="Run bootstrap shell",
        priority="critical",
        blocked_by=[prerequisite.id],
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic"),
        execution=TicketExecution(state="pending"),
    )

    assert pf.next_ticket() is None

    pf.update_ticket(
        prerequisite.id,
        status="done",
        execution=TicketExecution(state="done"),
    )

    next_ticket = pf.next_ticket()
    assert next_ticket is not None
    assert next_ticket.id == dependent.id


def test_ticket_execution_lifecycle_claim_start_complete(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Run bootstrap shell",
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/bootstrap.sh"),
        execution=TicketExecution(state="pending"),
    )

    claimed = pf.claim_ticket(ticket.id, assigned_to="koru-shell", lease_seconds=600)
    assert claimed is not None
    assert claimed.execution is not None
    assert claimed.execution.assigned_to == "koru-shell"
    assert claimed.execution.state == "ready"
    assert claimed.execution.lease_expires_at is not None

    started = pf.start_ticket(ticket.id)
    assert started is not None
    assert started.status == "in_progress"
    assert started.execution is not None
    assert started.execution.state == "running"
    assert started.execution.started_at is not None

    completed = pf.complete_ticket(
        ticket.id,
        note="Bootstrap completed successfully",
        artifacts=["reports/bootstrap.json"],
        result={"ok": True},
    )
    assert completed is not None
    assert completed.status == "done"
    assert completed.execution is not None
    assert completed.execution.state == "done"
    assert completed.execution.finished_at is not None
    assert completed.outputs is not None
    assert completed.outputs.notes == ["Bootstrap completed successfully"]
    assert completed.outputs.artifacts == ["reports/bootstrap.json"]
    assert completed.outputs.result == {"ok": True}


def test_ticket_execution_waiting_input_ready_and_fail(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Provide integration credentials",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive"),
        execution=TicketExecution(state="pending"),
    )

    waiting = pf.wait_for_input(
        ticket.id,
        prompt="Provide OPENROUTER_API_KEY",
        env_keys=["OPENROUTER_API_KEY"],
    )
    assert waiting is not None
    assert waiting.execution is not None
    assert waiting.execution.state == "waiting_input"
    assert waiting.inputs is not None
    assert waiting.inputs.prompt == "Provide OPENROUTER_API_KEY"
    assert waiting.inputs.env_keys == ["OPENROUTER_API_KEY"]

    ready = pf.ready_ticket(ticket.id)
    assert ready is not None
    assert ready.execution is not None
    assert ready.execution.state == "ready"

    failed = pf.fail_ticket(ticket.id, error="Remote API returned HTTP 502")
    assert failed is not None
    assert failed.execution is not None
    assert failed.execution.state == "failed"
    assert failed.execution.last_error == "Remote API returned HTTP 502"
    assert failed.execution.attempt == 1
