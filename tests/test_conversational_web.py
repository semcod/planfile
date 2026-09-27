"""Tests for conversational assistant and web interface in planfile."""

import pytest
from fastapi.testclient import TestClient

from planfile.api.server import app
from planfile.dsl import DSLExecutor


@pytest.fixture
def dsl_executor(tmp_path):
    from planfile import Planfile
    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="Normal task", priority="normal", sprint="current")
    pf.create_ticket(name="Critical bug", priority="critical", sprint="current")
    t_blocked = pf.create_ticket(name="Blocked task", priority="high", sprint="current")
    pf.block_ticket(t_blocked.id, reason="Waiting on migration")

    return DSLExecutor(project_path=str(tmp_path))


def test_conversational_blocked_queries(dsl_executor):
    res = dsl_executor.run("co jest zablokowane?")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert "Znaleziono 1 zablokowane zadanie" in res.message
    assert any(t["name"] == "Blocked task" for t in res.data)


def test_conversational_next_task(dsl_executor):
    res = dsl_executor.run("co jest następne?")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert "Następne rekomendowane zadanie" in res.message
    assert "Critical bug" in res.message


def test_conversational_sprint_summary(dsl_executor):
    res = dsl_executor.run("stan sprintu")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert "Stan sprintu: 3 zadań" in res.message
    assert res.data["total"] == 3
    assert res.data["blocked"] == 1


def test_conversational_high_priority(dsl_executor):
    res = dsl_executor.run("wysoki priorytet")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert "Aktywne zadania o wysokim priorytecie" in res.message
    assert any(t["name"] == "Critical bug" for t in res.data)


def test_web_dashboard_contains_assistant_interface():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    # Verify presence of conversational assistant panel and voice button
    assert 'id="assistant-panel"' in html
    assert 'id="chat-input"' in html
    assert 'id="mic-btn"' in html
    assert 'id="assistant-suggestions"' in html
    assert 'Rozmawiaj z planem' in html


def test_web_query_api_conversational(tmp_path):
    from planfile import Planfile
    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="Sample Task", priority="normal", sprint="current")
    client = TestClient(app)
    response = client.post("/query", json={"query": "stan sprintu", "project_path": str(tmp_path), "allow_llm_fallback": False})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["source_layer"] == "conversational_fast_path"
    assert "Stan sprintu" in payload["message"]


def test_conversational_create_ticket_proposal(dsl_executor):
    res = dsl_executor.run("dodaj zadanie Naprawić autoryzację z priorytetem wysokim")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert res.command["verb"] == "action_proposal"
    assert res.command["action"]["type"] == "create_ticket"
    assert res.command["action"]["name"] == "Naprawić autoryzację"
    assert res.command["action"]["priority"] == "high"
    assert "Czy chcesz utworzyć zadanie 'Naprawić autoryzację'" in res.message
    assert res.data["proposal"] is True


def test_conversational_mark_done_proposal(dsl_executor):
    res = dsl_executor.run("oznacz zadanie PLF-1 jako zrobione")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert res.command["verb"] == "action_proposal"
    assert res.command["action"]["type"] == "update_status"
    assert res.command["action"]["ticket_id"] == "PLF-1"
    assert res.command["action"]["status"] == "done"
    assert "Czy chcesz oznaczyć zadanie PLF-1 jako wykonane (done)?" in res.message


def test_conversational_change_priority_proposal(dsl_executor):
    res = dsl_executor.run("zmień priorytet PLF-2 na krytyczny")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert res.command["verb"] == "action_proposal"
    assert res.command["action"]["type"] == "change_priority"
    assert res.command["action"]["ticket_id"] == "PLF-2"
    assert res.command["action"]["priority"] == "critical"
    assert "Czy chcesz zmienić priorytet zadania PLF-2 na 'critical'?" in res.message


def test_conversational_block_ticket_proposal(dsl_executor):
    res = dsl_executor.run("zablokuj zadanie PLF-3 z powodu błędu bazy danych")
    assert res.ok is True
    assert res.source_layer == "conversational_fast_path"
    assert res.command["verb"] == "action_proposal"
    assert res.command["action"]["type"] == "block_ticket"
    assert res.command["action"]["ticket_id"] == "PLF-3"
    assert res.command["action"]["reason"] == "błędu bazy danych"
    assert "Czy chcesz zablokować zadanie PLF-3" in res.message


def test_assistant_execute_endpoints(tmp_path):
    from planfile import Planfile
    Planfile(str(tmp_path))
    client = TestClient(app)

    # 1. Create ticket via assistant execute
    create_resp = client.post("/api/assistant/execute", json={
        "action": "create_ticket",
        "name": "Wygenerowane przez asystenta",
        "priority": "high",
        "project_path": str(tmp_path),
    })
    assert create_resp.status_code == 200
    create_data = create_resp.json()
    assert create_data["ok"] is True
    t_id = create_data["ticket"]["id"]
    assert create_data["ticket"]["name"] == "Wygenerowane przez asystenta"
    assert create_data["ticket"]["priority"] == "high"

    # 2. Change priority
    prio_resp = client.post("/api/assistant/execute", json={
        "action": "change_priority",
        "ticket_id": t_id,
        "priority": "critical",
        "project_path": str(tmp_path),
    })
    assert prio_resp.status_code == 200
    prio_data = prio_resp.json()
    assert prio_data["ok"] is True
    assert prio_data["ticket"]["priority"] == "critical"

    # 3. Block ticket
    block_resp = client.post("/api/assistant/execute", json={
        "action": "block_ticket",
        "ticket_id": t_id,
        "reason": "Oczekiwanie na certyfikat SSL",
        "project_path": str(tmp_path),
    })
    assert block_resp.status_code == 200
    block_data = block_resp.json()
    assert block_data["ok"] is True
    assert block_data["ticket"]["status"] == "blocked"

    # 4. Mark done
    done_resp = client.post("/api/assistant/execute", json={
        "action": "update_status",
        "ticket_id": t_id,
        "status": "done",
        "project_path": str(tmp_path),
    })
    assert done_resp.status_code == 200
    done_data = done_resp.json()
    assert done_data["ok"] is True
    assert done_data["ticket"]["status"] == "done"

