"""CLI ``ticket next --format json`` when no runnable ticket exists."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
import typer


def test_ticket_next_json_prints_null_when_no_runnable(monkeypatch, capsys) -> None:
    import planfile

    fake_pf = MagicMock()
    fake_pf.next_ticket.return_value = None
    monkeypatch.setattr(planfile.Planfile, "auto_discover", lambda: fake_pf)

    from planfile.cli.groups.ticket.commands import ticket_next

    with pytest.raises(typer.Exit) as excinfo:
        ticket_next(sprint="current", queue=None, fmt="json")
    assert excinfo.value.exit_code == 0
    out = capsys.readouterr().out.strip()
    assert json.loads(out) is None
