import json

import pytest

from planfile import Planfile
from planfile.core.operational_dsl import line, parse, serialize


def test_sodl_round_trip_and_tamper_detection():
    value = line(timestamp="2026-07-21T17:00:00Z", kind="task", ticket_id="PLF-1", actor="bot:test", oql="ticket.update", uri="planfile://tickets/PLF-1/command/update", data={"note": "zażółć", "timeout": 30.0})
    assert serialize(parse(value)) == value
    assert parse(value)["data"]["timeout"] == 30
    try:
        parse(value.replace("status=recorded", "status=changed"))
    except ValueError as exc:
        assert str(exc) == "sodl_event_hash_invalid"
    else:
        raise AssertionError("tampered line was accepted")


def test_ticket_creation_and_history_have_replayable_dsl(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Governed task")
    created = parse(ticket.dsl)
    assert created["oql"] == "ticket.create"
    assert created["ticket_id"] == ticket.id
    updated = pf.update_ticket(ticket.id, priority="high", actor="bot:test", reason="triage")
    journal = pf.store.operational_events(ticket_id=ticket.id)
    assert [row["event"]["oql"] for row in journal] == ["ticket.update", "ticket.create"]

    # The replayable line lives in the journal only. Storing a second copy on
    # the ticket made history 75% of subactor's sprint file, and every write
    # re-serialises the whole file. History keeps the audit metadata.
    replayed = parse(journal[0]["dsl"])
    assert replayed["oql"] == "ticket.update"
    assert replayed["data"]["payload"]["reason"] == "triage"
    entry = updated.history[-1]
    assert "dsl" not in entry
    assert entry["changes"] == ["priority"]
    assert (entry["reason"], entry["actor"]) == ("triage", "bot:test")


@pytest.mark.parametrize("radar_available", [False, True])
def test_ticket_dsl_redacts_nested_credentials(tmp_path, monkeypatch, radar_available):
    from planfile.core import ticket_radar

    def assessment(payload, root, deadline):
        if not radar_available:
            raise FileNotFoundError("optional radar unavailable")
        result = {
            "schema": "subactor.ticket-radar/v1",
            "ticket_ref": json.loads(payload)["id"],
            "complexity": "S",
            "score": 12,
            "estimate": {"minutes": 10},
            "split": {"recommended": False},
        }
        return json.dumps({
            "schema": "subactor.ticket-radar-bundle/v1", "jsonl": json.dumps(result),
        }).encode()

    monkeypatch.setattr(ticket_radar, "_bundle", assessment)
    pf = Planfile(str(tmp_path))
    human_description = "https://founder.test/#token=placeholder-redaction-example"
    redacted_description = human_description.replace("placeholder-redaction-example", "[REDACTED]")
    ticket = pf.create_ticket(name="Secret-safe", description=human_description, sync={"password": "hidden"})
    # Journal redaction must preserve the original model values and human text.
    assert ticket.description.split("\n\n", 1)[0] == human_description
    assert ticket.sync["password"] == "hidden"
    event = parse(ticket.dsl)
    description = event["data"]["payload"]["description"]
    assert description.split("\n\n", 1)[0] == redacted_description
    if radar_available:
        assert "**Ticket impact radar (advisory)**" in description
        assert "Score: `12/100`" in description
        assert "does not grant execution, review or merge authority" in description
    else:
        assert description == redacted_description
    assert event["data"]["payload"]["sync"]["password"] == "[REDACTED]"
    # Inspect decoded data, since a random event digest may contain short text.
    assert "placeholder-redaction-example" not in json.dumps(event["data"])
    assert '"hidden"' not in json.dumps(event["data"])


def test_move_and_delete_are_journaled_but_delete_is_not_replayable(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Move then delete")
    assert pf.store.move_ticket(ticket.id, "backlog") is True
    assert pf.store.delete_ticket(ticket.id) is True
    events = [row["event"] for row in pf.store.operational_events(ticket_id=ticket.id)]
    assert [event["oql"] for event in events] == ["ticket.delete", "ticket.update", "ticket.create"]
    assert events[0]["replayable"] is False
