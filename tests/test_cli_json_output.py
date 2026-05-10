"""CLI JSON output should remain machine-parseable."""

from __future__ import annotations

import json

from planfile import Ticket
from planfile.cli.groups.ticket.commands import _display_tickets


def test_ticket_list_json_output_is_parseable(capsys):
    long_description = (
        "This description is intentionally long enough to trigger Rich wrapping "
        "when JSON is printed through console.print instead of plain stdout. "
        "Koru and other automation tools consume this command as JSON."
    )
    ticket = Ticket(
        id="PLF-001",
        name="Keep planfile JSON machine-readable",
        description=long_description,
        labels=["koru", "automation"],
    )

    _display_tickets([ticket], "json")

    parsed = json.loads(capsys.readouterr().out)
    assert parsed[0]["id"] == "PLF-001"
    assert parsed[0]["description"] == long_description
    assert parsed[0]["labels"] == ["koru", "automation"]
