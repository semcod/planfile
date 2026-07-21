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
    history = parse(updated.history[-1]["dsl"])
    assert history["oql"] == "ticket.update"
    assert history["data"]["payload"]["reason"] == "triage"
    journal = pf.store.operational_events(ticket_id=ticket.id)
    assert [row["event"]["oql"] for row in journal] == ["ticket.update", "ticket.create"]


def test_ticket_dsl_redacts_nested_credentials(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Secret-safe", description="https://founder.test/#token=abc", sync={"password": "hidden"})
    assert "abc" not in ticket.dsl
    assert "hidden" not in ticket.dsl
    event = parse(ticket.dsl)
    assert event["data"]["payload"]["sync"]["password"] == "[REDACTED]"


def test_move_and_delete_are_journaled_but_delete_is_not_replayable(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Move then delete")
    assert pf.store.move_ticket(ticket.id, "backlog") is True
    assert pf.store.delete_ticket(ticket.id) is True
    events = [row["event"] for row in pf.store.operational_events(ticket_id=ticket.id)]
    assert [event["oql"] for event in events] == ["ticket.delete", "ticket.update", "ticket.create"]
    assert events[0]["replayable"] is False
