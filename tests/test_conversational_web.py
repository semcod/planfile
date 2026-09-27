"""Tests for conversational assistant and web interface in planfile."""

import pytest
from fastapi.testclient import TestClient

from planfile.dsl import DSLExecutor
from planfile.api.server import app


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
