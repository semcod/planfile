"""CLI ``ticket next --count`` and ``ticket waves`` tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
import typer
import yaml


def test_ticket_next_batch_json(monkeypatch, capsys) -> None:
    import planfile
    from planfile.cli.groups.ticket.commands import ticket_next

    ticket1 = MagicMock()
    ticket1.model_dump.return_value = {"id": "T-01", "name": "Task 1"}
    ticket2 = MagicMock()
    ticket2.model_dump.return_value = {"id": "T-02", "name": "Task 2"}

    fake_pf = MagicMock()
    fake_pf.next_tickets.return_value = [ticket1, ticket2]
    monkeypatch.setattr(planfile.Planfile, "auto_discover", lambda: fake_pf)

    ticket_next(sprint="current", queue="backend", count=2, disjoint_files=True, fmt="json", debug=False)
    fake_pf.next_tickets.assert_called_once_with(
        count=2,
        sprint="current",
        queue="backend",
        disjoint_files=True,
    )
    out = capsys.readouterr().out.strip()
    data = json.loads(out)
    assert len(data) == 2
    assert data[0]["id"] == "T-01"
    assert data[1]["id"] == "T-02"


def test_ticket_next_batch_empty_json(monkeypatch, capsys) -> None:
    import planfile
    from planfile.cli.groups.ticket.commands import ticket_next

    fake_pf = MagicMock()
    fake_pf.next_tickets.return_value = []
    monkeypatch.setattr(planfile.Planfile, "auto_discover", lambda: fake_pf)

    with pytest.raises(typer.Exit) as excinfo:
        ticket_next(count=3, fmt="json")
    assert excinfo.value.exit_code == 0
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == []


def test_ticket_next_batch_yaml(monkeypatch, capsys) -> None:
    import planfile
    from planfile.cli.groups.ticket.commands import ticket_next

    ticket1 = MagicMock()
    ticket1.model_dump.return_value = {"id": "T-01", "name": "Task 1"}
    fake_pf = MagicMock()
    fake_pf.next_tickets.return_value = [ticket1]
    monkeypatch.setattr(planfile.Planfile, "auto_discover", lambda: fake_pf)

    ticket_next(count=2, fmt="yaml")
    out = capsys.readouterr().out.strip()
    parsed = yaml.safe_load(out)
    assert isinstance(parsed, list)
    assert parsed[0]["id"] == "T-01"


def test_ticket_waves_json(monkeypatch, capsys) -> None:
    import planfile
    from planfile.cli.groups.ticket.commands import ticket_waves

    fake_pf = MagicMock()
    fake_pf.execution_waves.return_value = [["T-01", "T-02"], ["T-03"]]
    monkeypatch.setattr(planfile.Planfile, "auto_discover", lambda: fake_pf)

    ticket_waves(sprint="current", fmt="json")
    fake_pf.execution_waves.assert_called_once_with(sprint="current")
    out = capsys.readouterr().out.strip()
    waves = json.loads(out)
    assert waves == [["T-01", "T-02"], ["T-03"]]


def test_ticket_waves_table(monkeypatch, capsys) -> None:
    import planfile
    from planfile.cli.groups.ticket.commands import ticket_waves

    fake_pf = MagicMock()
    fake_pf.execution_waves.return_value = [["T-01", "T-02"], ["T-03"]]
    monkeypatch.setattr(planfile.Planfile, "auto_discover", lambda: fake_pf)

    ticket_waves(sprint="sprint-1", fmt="table")
    out = capsys.readouterr().out
    assert "Wave 1" in out
    assert "Wave 2" in out
    assert "T-01, T-02" in out
    assert "T-03" in out
