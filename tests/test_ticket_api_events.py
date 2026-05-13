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


def test_ticket_lifecycle_api_persists_history_for_detail_panel(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Needs durable history",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="default", state="pending"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.post(
        f"/tickets/{ticket.id}/claim",
        json={"assigned_to": "koru-shell"},
    ).status_code == 200
    assert client.post(
        f"/tickets/{ticket.id}/input-required",
        json={"prompt": "Provide API key", "env_keys": ["OPENROUTER_API_KEY"]},
    ).status_code == 200

    loaded = client.get(f"/tickets/{ticket.id}").json()

    assert [entry["action"] for entry in loaded["history"]] == ["update", "update"]
    assert loaded["history"][0]["changes"] == ["execution"]
    assert loaded["history"][0]["execution_state"] == "ready"
    assert loaded["history"][1]["execution_state"] == "waiting_input"
    assert loaded["history"][1]["previous_execution_state"] == "ready"


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
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert "planfile queue dashboard" in response.text
    assert "Notification.requestPermission" in response.text
    assert "new WebSocket" in response.text
    assert "queue-filter" in response.text
    assert "status-filter" in response.text
    assert "Test notification" in response.text
    assert "setInterval" in response.text
    assert "loadEventHistory" in response.text
    assert "applyUrlState" in response.text
    assert "syncUrlState" in response.text
    assert 'params.set("ticket", state.selectedTicketId)' in response.text
    assert 'params.set("queue", state.queue)' in response.text
    assert 'params.set("status", state.statusFilter)' in response.text
    assert 'params.set("tab", state.detailTab)' in response.text
    assert "/events?limit=100" in response.text
    assert "Ticket Detail" in response.text
    assert "ticket-detail" in response.text
    assert "data-detail-tab" in response.text
    assert "Tool logs" in response.text
    assert "Raw JSON" in response.text
    assert "data-ticket-id" in response.text
    assert "function selectTicket(ticketId" in response.text
    assert "/events?ticket_id=" in response.text
    assert "renderTicketTimeline" in response.text
    assert "Related tickets and splits" in response.text
    assert '{ cache: "no-store" }' in response.text
    assert "scanTicketStatuses" in response.text
    assert "Ticket status changes and errors" in response.text
    assert "management.event" in response.text
    assert "if (event?.queue) return String(event.queue);" in response.text
    assert "function isRunningTicket(ticket)" in response.text
    assert "function ticketMatchesStatus(ticket)" in response.text
    assert 'localStorage.setItem("planfile.statusFilter", state.statusFilter)' in response.text
    assert 'ticket?.status === "in_progress"' in response.text
    assert "if (isWaitingTicket(ticket) || isFailedTicket(ticket) || stateName === \"done\") return false;" in response.text
    assert "const running = visibleTickets.filter(isRunningTicket).length;" in response.text
    assert "/runtime-context" in response.text


def test_runtime_context_api_and_page(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    page = client.get("/runtime-context")
    assert page.status_code == 200
    assert "Topology / Runtime Context" in page.text
    assert "/api/runtime-context" in page.text

    response = client.get("/api/runtime-context")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_root"] == str(tmp_path.resolve())
    assert payload["summary"]["project"] == tmp_path.name
    assert payload["config"]["enabled"]["systems"] is True

    update = client.put(
        "/api/runtime-context/config",
        json={"enabled": {"systems": False, "pipelines": True}, "overrides": {"note": "test"}},
    )
    assert update.status_code == 200
    saved = update.json()
    assert saved["enabled"]["systems"] is False
    assert saved["enabled"]["pipelines"] is True
    assert saved["overrides"]["note"] == "test"

    refreshed = client.get("/api/runtime-context").json()
    assert refreshed["config"]["enabled"]["systems"] is False
    assert refreshed["systems"] == []


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

    all_response = client.get("/events")
    refactor_response = client.get("/events?queue=c2004-refactor")
    all_events = all_response.json()
    refactor_events = refactor_response.json()

    assert all_response.headers["cache-control"] == "no-store, max-age=0"
    assert refactor_response.headers["cache-control"] == "no-store, max-age=0"
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


def test_management_event_api_broadcasts_records_and_filters_by_queue():
    server._manager.active.clear()
    server._event_history.clear()

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.post(
            "/events/ingest",
            json={
                "source": "koru",
                "tool": "koru.queue",
                "action": "completed",
                "ticket_id": "PLF-074",
                "status": "completed",
                "level": "info",
                "queue": "c2004-runtime",
                "message": "Executed PLF-074",
                "details": {"executor": "shell"},
            },
        )

        assert response.status_code == 200
        event = ws.receive_json()

    runtime_events = client.get("/events?queue=c2004-runtime").json()
    default_events = client.get("/events?queue=default").json()

    assert event["type"] == "management.event"
    assert event["tool"] == "koru.queue"
    assert event["action"] == "completed"
    assert event["queue"] == "c2004-runtime"
    assert event["ticket_id"] == "PLF-074"
    assert event["details"]["ticket_id"] == "PLF-074"
    assert runtime_events[-1]["type"] == "management.event"
    assert default_events == []


def test_events_api_filters_management_events_by_ticket_id():
    server._manager.active.clear()
    server._event_history.clear()

    client = TestClient(server.app)

    assert client.post(
        "/events/ingest",
        json={
            "source": "koru",
            "tool": "koru.shell",
            "action": "step-log",
            "status": "warning",
            "level": "warning",
            "queue": "c2004-refactor",
            "message": "human input required before continuing",
            "details": {"ticket_id": "PLF-070", "split_ticket_id": "PLF-077"},
        },
    ).status_code == 200
    assert client.post(
        "/events/ingest",
        json={
            "source": "koru",
            "tool": "koru.shell",
            "action": "step-log",
            "status": "info",
            "level": "info",
            "queue": "c2004-runtime",
            "message": "unrelated",
            "details": {"ticket_id": "PLF-074"},
        },
    ).status_code == 200

    response = client.get("/events?ticket_id=PLF-070")
    events = response.json()

    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert len(events) == 1
    assert events[0]["ticket_id"] == "PLF-070"
    assert events[0]["details"]["split_ticket_id"] == "PLF-077"
    assert client.get("/events?ticket_id=PLF-999").json() == []


def test_tickets_api_reads_updated_store_and_disables_cache(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Status changes outside dashboard",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="default", state="ready"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    first = client.get("/tickets?sprint=all")
    pf.complete_ticket(ticket.id, note="done outside API")
    second = client.get("/tickets?sprint=all")

    assert first.headers["cache-control"] == "no-store, max-age=0"
    assert second.headers["cache-control"] == "no-store, max-age=0"
    assert next(item for item in first.json() if item["id"] == ticket.id)["status"] == "open"
    assert next(item for item in second.json() if item["id"] == ticket.id)["status"] == "done"


def test_post_tickets_creates_ticket_via_json_api(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    response = client.post(
        "/tickets",
        json={
            "name": "Created from REST",
            "description": "via dashboard API",
            "priority": "high",
            "sprint": "current",
            "labels": ["dashboard", "api"],
            "executor": {"kind": "human", "mode": "interactive"},
            "execution": {"queue": "default", "state": "ready"},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Created from REST"
    assert data["id"]
    assert data["execution"]["queue"] == "default"
    assert data["executor"]["kind"] == "human"

    listed = client.get("/tickets?sprint=all").json()
    assert any(t["id"] == data["id"] for t in listed)
