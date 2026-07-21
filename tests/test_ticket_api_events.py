"""API/WebSocket tests for ticket execution events."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient

from planfile import Planfile, TicketExecution, TicketExecutor, TicketInputs, TicketSource
from planfile.api import server


def _completion_receipt(ticket_id: str) -> dict:
    return {
        "schema": "subactor.completion-receipt.v1",
        "ticket_id": ticket_id,
        "outcome": "succeeded",
        "actor": "bot:test",
        "reason": "Expected state was observed.",
        "completed_at": "2026-07-20T21:00:00Z",
        "eql": [{"id": "expected-state", "passed": True, "expected": True, "actual": True}],
        "artifacts": ["audit:test"],
    }


def test_governed_ticket_requires_completion_receipt(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Governed process",
        labels=["process-envelope:v2"],
        execution=TicketExecution(state="running"),
        inputs=TicketInputs(
            process_manifest={
                "schema": "subactor.process-envelope.v2",
                "reason": "Governed test",
                "requested_by": "bot:test",
                "definitions": {"aql": [{}], "eql": [{}], "oql": [{}], "uri": [{}]},
            }
        ),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.post(f"/tickets/{ticket.id}/done").status_code == 409
    assert client.post(f"/tickets/{ticket.id}/complete", json={"result": {"ok": True}}).status_code == 409

    receipt = _completion_receipt(ticket.id)
    response = client.post(
        f"/tickets/{ticket.id}/complete",
        json={"note": "Verified", "result": {"ok": True}, "artifacts": ["audit:test"], "completion_receipt": receipt},
    )
    assert response.status_code == 200
    completed = response.json()
    assert completed["outputs"]["completion_receipt"] == receipt
    assert completed["history"][-1]["actor"] == "bot:test"
    assert completed["history"][-1]["reason"] == "Expected state was observed."


def test_governed_ticket_mutations_require_attributed_history(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    uri = {"id": "read-time", "name": "Read time", "uri": "time://clock/query/now"}
    ticket = pf.create_ticket(
        name="Governed history",
        labels=["process-envelope:v2"],
        execution=TicketExecution(state="running", max_attempts=2),
        inputs=TicketInputs(
            uri_processes=[uri],
            process_manifest={
                "schema": "subactor.process-envelope.v2",
                "reason": "Governed history test",
                "requested_by": "bot:test",
                "definitions": {"aql": [{}], "eql": [{}], "oql": [{}], "uri": [uri]},
            },
        ),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.patch(f"/tickets/{ticket.id}", json={"priority": "high"}).status_code == 422
    assert client.post(f"/tickets/{ticket.id}/fail", json={"error": "temporary"}).status_code == 422
    updated = client.patch(
        f"/tickets/{ticket.id}",
        json={"priority": "high", "actor": "bot:test", "reason": "Escalated priority after preflight."},
    )
    assert updated.status_code == 200
    assert updated.json()["history"][-1]["actor"] == "bot:test"
    assert updated.json()["history"][-1]["reason"] == "Escalated priority after preflight."


def test_governed_ticket_creation_requires_structured_four_part_envelope(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    invalid = client.post(
        "/tickets",
        json={
            "name": "Incomplete governed process",
            "labels": ["process-envelope:v2"],
            "inputs": {
                "process_manifest": {
                    "schema": "subactor.process-envelope.v2",
                    "reason": "test",
                    "requested_by": "bot:test",
                    "definitions": {"aql": [{}], "eql": [], "oql": [{}], "uri": [{}]},
                }
            },
        },
    )
    assert invalid.status_code == 422
    assert "process_definitions_incomplete:eql" in invalid.json()["detail"]

    uri = {"id": "read-time", "name": "Read time", "uri": "time://clock/query/now"}
    valid = client.post(
        "/tickets",
        json={
            "name": "Complete governed process",
            "labels": ["process-envelope:v2"],
            "inputs": {
                "uri_processes": [uri],
                "process_manifest": {
                    "schema": "subactor.process-envelope.v2",
                    "reason": "test",
                    "requested_by": "bot:test",
                    "definitions": {"aql": [{}], "eql": [{}], "oql": [{}], "uri": [uri]},
                },
            },
        },
    )
    assert valid.status_code == 201


def test_production_gate_rejects_every_legacy_ticket_creation(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setenv("PLANFILE_REQUIRE_PROCESS_ENVELOPE", "1")
    client = TestClient(server.app)

    response = client.post("/tickets", json={"name": "Legacy ticket"})

    assert response.status_code == 422
    assert response.json()["detail"] == "process_envelope_required"


def test_production_gate_does_not_freeze_existing_legacy_ticket(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Existing legacy ticket")
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setenv("PLANFILE_REQUIRE_PROCESS_ENVELOPE", "1")
    client = TestClient(server.app)

    response = client.patch(
        f"/tickets/{ticket.id}",
        json={
            "status": "failed",
            "actor": "automation:legacy-migration",
            "reason": "Normalize an exhausted legacy execution.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["execution"]["state"] == "failed"


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


def test_ticket_response_api_defaults_to_ready_and_broadcasts(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Human response",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(queue="founder", state="waiting_input"),
    )
    server._manager.active.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True
        response = client.post(
            f"/tickets/{ticket.id}/respond",
            json={"note": "Proceed with the requested access.", "actor": "founder"},
        )
        event = ws.receive_json()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "open"
    assert payload["execution"]["state"] == "ready"
    assert payload["outputs"]["notes"] == ["Proceed with the requested access."]
    assert event["action"] == "respond"
    assert event["ticket"]["execution"]["state"] == "ready"


def test_ticket_response_api_null_state_preserves_current_status(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Add context without changing status",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(queue="founder", state="running", assigned_to="founder"),
        status="in_progress",
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post(
        f"/tickets/{ticket.id}/respond",
        json={"note": "Additional context only.", "next_state": None, "actor": "founder"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["execution"]["state"] == "running"
    assert payload["execution"]["assigned_to"] == "founder"
    assert payload["outputs"]["notes"] == ["Additional context only."]


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
    assert "Copy JSON to clipboard" in response.text
    assert "function installCopyControls" in response.text
    assert 'pre:not([data-copy-enhanced])' in response.text
    assert "copy-inline-control" in response.text
    assert "Manage actor permissions" in response.text
    assert "Delegation manager" in response.text
    assert 'href="${escapeHtml(accessHref)}"' in response.text
    assert "Respond to this ticket" in response.text
    assert "data-ticket-response-form" in response.text
    assert "Delegate to actor / queue" in response.text
    assert 'name="delegate_to"' in response.text
    assert '<select id="ticket-delegate-to" name="delegate_to"' in response.text
    assert 'name="delegate_kind"' not in response.text
    assert 'fetch("/delegation/actors"' in response.text
    assert "URI Process plan" in response.text
    assert '<option value="" selected>Keep current status</option>' in response.text
    assert '<option value="ready">READY' in response.text
    assert 'value="in_progress"' in response.text
    assert "/respond" in response.text
    assert "beginTicketWork" not in response.text
    assert "data-start-ticket" in response.text
    assert "async function startSelectedTicket" in response.text
    assert "/start" in response.text
    assert ".slice(0, 80)" not in response.text
    assert "tickets-count" in response.text
    assert "copyTicketDetailJson" in response.text
    assert "ticketDetailExportPayload" in response.text
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


def test_access_panel_redirects_to_configured_aql_actor_editor(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANFILE_ACCESS_PANEL_URL", "https://control.example.test/panel?source=planfile")
    catalogue = tmp_path / "actors.json"
    catalogue.write_text(
        json.dumps({"actors": [{"id": "administrator-bot", "label": "Administrator", "kind": "bot"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLANFILE_DELEGATION_ACTORS_FILE", str(catalogue))
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/access-panel?actor=administrator-bot", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == (
        "https://control.example.test/panel?source=planfile&tab=access&action=edit&actor=administrator-bot"
    )
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert client.get("/access-panel?actor=unknown", follow_redirects=False).status_code == 422
    manager = client.get("/access-panel?view=delegation", follow_redirects=False)
    assert manager.status_code == 307
    assert "tab=delegation&action=view" in manager.headers["location"]


def test_delegation_actor_catalog_api_and_validation(tmp_path, monkeypatch):
    catalogue = tmp_path / "delegation-actors.json"
    catalogue.write_text(json.dumps({"actors": [
        {"id": "founder", "label": "Founder", "kind": "human"},
        {"id": "project-operator-bot", "label": "Project operator", "kind": "bot"},
    ]}))
    monkeypatch.setenv("PLANFILE_DELEGATION_ACTORS_FILE", str(catalogue))
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Delegate through API", source=TicketSource(tool="human"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    actors = client.get("/delegation/actors")
    assert actors.status_code == 200
    assert [actor["id"] for actor in actors.json()] == ["founder", "project-operator-bot"]

    rejected = client.post(f"/tickets/{ticket.id}/respond", json={
        "note": "Invalid delegation", "delegate_to": "invented-person",
    })
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "ticket_delegate_not_allowed:invented-person"

    delegated = client.post(f"/tickets/{ticket.id}/respond", json={
        "note": "Run the project", "delegate_to": "project-operator-bot",
    })
    assert delegated.status_code == 200
    assert delegated.json()["executor"] == {
        "kind": "bot", "mode": "automatic", "handler": "project-operator-bot"
    }


def test_runtime_context_api_and_page(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    page = client.get("/runtime-context")
    assert page.status_code == 200
    assert "Topology / Runtime Context" in page.text
    assert "/api/runtime-context" in page.text
    assert "function installCopyBlocks" in page.text
    assert "copyable-code" in page.text

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


def test_runtime_context_get_does_not_create_config(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    config_path = tmp_path / ".koru" / "runtime-context.json"
    assert client.get("/api/runtime-context/config").status_code == 200
    assert not config_path.exists()


def test_runtime_context_discovers_monorepo_and_redacts_compose_environment(tmp_path, monkeypatch):
    (tmp_path / "service").mkdir()
    (tmp_path / "service" / "package.json").write_text(
        json.dumps({"name": "child-service", "version": "1.2.3"}),
        encoding="utf-8",
    )
    (tmp_path / "platform").mkdir()
    (tmp_path / "platform" / "docker-compose.yml").write_text(
        "services:\n  api:\n    environment:\n      API_TOKEN: super-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLANFILE_RUNTIME_CONTEXT_PROJECT_NAME", "example-monorepo")

    context = server.build_runtime_context(tmp_path)

    assert context["summary"]["project"] == "example-monorepo"
    assert context["summary"]["workspaces"] == 1
    assert context["systems"][0]["compose_files"] == ["platform/docker-compose.yml"]
    assert context["systems"][0]["environment"] == {"API_TOKEN": "<redacted>"}


def test_openapi_and_health_publish_same_version():
    client = TestClient(server.app)

    assert client.get("/openapi.json").json()["info"]["version"] == client.get("/health").json()["version"]


def test_ticket_list_pagination_headers(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    for index in range(3):
        pf.create_ticket(name=f"Ticket {index}", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/tickets?sprint=all&offset=1&limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["x-total-count"] == "3"
    assert response.headers["x-result-count"] == "1"


def test_move_ticket_api_and_sprint_validation(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Move through API", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    moved = client.post(f"/tickets/{ticket.id}/move?to_sprint=audit-sprint")

    assert moved.status_code == 200
    assert pf.get_ticket(ticket.id).sprint == "audit-sprint"
    assert client.post(f"/tickets/{ticket.id}/move?to_sprint=../../escape").status_code == 422
    assert client.post(
        "/tickets",
        json={"name": "Escape", "sprint": "../../escape"},
    ).status_code == 422


def test_sprint_api_uses_canonical_sprint_store(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="Current work", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    listed = client.get("/sprints")
    created = client.post(
        "/sprints",
        json={"id": "release-1", "name": "Release 1", "objectives": ["Ship"]},
    )

    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {"backlog", "current"}
    assert next(item for item in listed.json() if item["id"] == "current")["ticket_count"] == 1
    assert created.status_code == 201
    assert created.json()["id"] == "release-1"
    assert client.post(
        "/sprints",
        json={"id": "release-1", "name": "Duplicate"},
    ).status_code == 409
    assert {item["id"] for item in client.get("/sprints").json()} == {
        "backlog", "current", "release-1"
    }


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
