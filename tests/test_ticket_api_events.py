"""API/WebSocket tests for ticket execution events."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient

from planfile import Planfile, TicketExecution, TicketExecutor, TicketSource
from planfile.api import server


def test_lifecycle_api_broadcasts_ticket_execution_event(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Run bootstrap shell",
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic"),
        execution=TicketExecution(state="pending"),
    )

    server._manager.active.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.post(
            f"/tickets/{ticket.id}/claim",
            json={"assigned_to": "koru-shell", "lease_seconds": 60},
        )

        assert response.status_code == 200
        event = ws.receive_json()

    assert event["type"] == "ticket.execution.changed"
    assert event["action"] == "claim"
    assert event["ticket_id"] == ticket.id
    assert event["ticket"]["execution"]["state"] == "ready"
    assert event["ticket"]["execution"]["assigned_to"] == "koru-shell"


def test_ticket_update_api_broadcasts_ticket_changed_event(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Document bootstrap flow",
        source=TicketSource(tool="human"),
    )

    server._manager.active.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.patch(
            f"/tickets/{ticket.id}",
            json={"priority": "high"},
        )

        assert response.status_code == 200
        event = ws.receive_json()

    assert event["type"] == "ticket.changed"
    assert event["action"] == "update"
    assert event["ticket_id"] == ticket.id
    assert event["ticket"]["priority"] == "high"


def test_root_serves_queue_dashboard(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(
        name="Dashboard visible ticket",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="c2004-refactor", state="ready"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "planfile queue dashboard" in response.text
    assert "Notification.requestPermission" in response.text
    assert "new WebSocket" in response.text
    assert "queue-filter" in response.text
    assert "Test notification" in response.text
    assert "setInterval" in response.text
    assert "loadEventHistory" in response.text
    assert "/events?limit=100" in response.text


def test_favicon_returns_no_content():
    client = TestClient(server.app)
    response = client.get("/favicon.ico")

    assert response.status_code == 204


def test_next_ticket_api_filters_by_queue(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(
        name="Default queue",
        priority="critical",
        execution=TicketExecution(queue="default", state="ready"),
    )
    refactor = pf.create_ticket(
        name="Refactor queue",
        priority="high",
        execution=TicketExecution(queue="c2004-refactor", state="ready"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/tickets/next?queue=c2004-refactor")

    assert response.status_code == 200
    assert response.json()["id"] == refactor.id


def test_events_api_returns_recent_events_and_filters_by_queue(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    default_ticket = pf.create_ticket(
        name="Default event",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="default", state="pending"),
    )
    refactor_ticket = pf.create_ticket(
        name="Refactor event",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="c2004-refactor", state="pending"),
    )

    server._manager.active.clear()
    server._event_history.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.post(f"/tickets/{default_ticket.id}/ready").status_code == 200
    assert client.post(f"/tickets/{refactor_ticket.id}/ready").status_code == 200

    all_events = client.get("/events").json()
    refactor_events = client.get("/events?queue=c2004-refactor").json()

    assert [event["ticket_id"] for event in all_events][-2:] == [
        default_ticket.id,
        refactor_ticket.id,
    ]
    assert [event["ticket_id"] for event in refactor_events] == [refactor_ticket.id]
    assert "created_at" in refactor_events[0]


def test_test_event_api_broadcasts_and_records_synthetic_error():
    server._manager.active.clear()
    server._event_history.clear()

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.post(
            "/events/test",
            json={"queue": "c2004-runtime", "message": "Synthetic failure"},
        )

        assert response.status_code == 200
        event = ws.receive_json()

    history = client.get("/events?queue=c2004-runtime").json()

    assert event["type"] == "dashboard.test"
    assert event["ticket_id"] == "TEST"
    assert event["ticket"]["execution"]["state"] == "failed"
    assert event["ticket"]["execution"]["last_error"] == "Synthetic failure"
    assert history[-1]["type"] == "dashboard.test"
