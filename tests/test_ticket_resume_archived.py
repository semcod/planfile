from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
import yaml

from planfile import Planfile
from planfile.core.models import Ticket, TicketExecution
from planfile.core.store import ImmutableTerminalReopenError, Store


def test_resume_archived_unfinished_ticket_restores_current_runnability(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    old = datetime.now(timezone.utc) - timedelta(days=2)

    # Create an unfinished ticket that failed/blocked and was archived into history
    ticket = pf.create_ticket(
        name="Recoverable unfinished task",
        status="blocked",
        execution=TicketExecution(state="blocked", queue="default"),
    )
    history_sprint = f"history-{old:%Y-%m-%d}"
    moved = pf.store.move_ticket(ticket.id, history_sprint)
    assert moved is True

    # While archived, ticket is NOT in current sprint or runnable report
    current_tickets = pf.list_tickets(sprint="current")
    assert ticket.id not in [t.id for t in current_tickets]
    runnable = pf.runnable_report(sprint="current")
    assert ticket.id not in runnable["servable"]

    # Resume the ticket
    resumed = pf.resume_ticket(ticket.id, note="Unblocked after dependency fix")
    assert resumed is not None
    assert resumed.id == ticket.id
    assert resumed.status.value == "open"
    assert resumed.execution.state == "ready"
    assert resumed.sprint == "current"

    # Ticket is now admitted in current sprint and runnable report
    current_tickets_after = pf.list_tickets(sprint="current")
    assert ticket.id in [t.id for t in current_tickets_after]
    runnable_after = pf.runnable_report(sprint="current")
    assert ticket.id in runnable_after["servable"]
    next_up = pf.next_ticket(sprint="current")
    assert next_up is not None
    assert next_up.id == ticket.id


def test_ready_ticket_on_archived_ticket_restores_to_current(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Task to ready",
        status="open",
        execution=TicketExecution(state="failed", queue="default"),
    )
    # Move to history
    pf.store.move_ticket(ticket.id, "history-2026-10-01")
    assert ticket.id not in [t.id for t in pf.list_tickets(sprint="current")]

    # ready_ticket restores it to current
    ready = pf.ready_ticket(ticket.id)
    assert ready is not None
    assert ready.status.value == "open"
    assert ready.execution.state == "ready"
    assert ready.sprint == "current"
    assert ticket.id in [t.id for t in pf.list_tickets(sprint="current")]


def test_resume_rejects_completed_or_canceled_ticket(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    done_ticket = pf.create_ticket(name="Done task", status="done")
    canceled_ticket = pf.create_ticket(name="Canceled task", status="canceled")

    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.resume_ticket(done_ticket.id)

    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.resume_ticket(canceled_ticket.id)

    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.ready_ticket(done_ticket.id)


def test_cli_ticket_resume_command(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner
    from planfile.cli.commands import app

    runner = CliRunner()
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="CLI Resumed task",
        status="open",
        execution=TicketExecution(state="failed", queue="default"),
    )
    pf.store.move_ticket(ticket.id, "history-2026-10-01")

    # Change working directory in test runner
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ticket", "resume", ticket.id, "-n", "resumed via CLI"])
    assert result.exit_code == 0
    assert "Resumed" in result.output

    reloaded = pf.get_ticket(ticket.id)
    assert reloaded.sprint == "current"
    assert reloaded.execution.state == "ready"


def test_resume_archived_unfinished_ticket_sharded_storage(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    pf.store.migrate_to_sharded_yaml(shard_size=10)

    ticket = pf.create_ticket(
        name="Sharded recoverable task",
        status="blocked",
        execution=TicketExecution(state="blocked", queue="default"),
    )
    pf.store.move_ticket(ticket.id, "history-2026-10-02")
    assert ticket.id not in [t.id for t in pf.list_tickets(sprint="current")]

    resumed = pf.resume_ticket(ticket.id)
    assert resumed is not None
    assert resumed.sprint == "current"
    assert resumed.status.value == "open"
    assert resumed.execution.state == "ready"
    assert ticket.id in [t.id for t in pf.list_tickets(sprint="current")]
    runnable = pf.runnable_report(sprint="current")
    assert ticket.id in runnable["servable"]

