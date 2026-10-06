"""Unit and integration tests for GET /api/voice-digest endpoint."""

import pytest
from starlette.testclient import TestClient

from planfile import Planfile
from planfile.api.server import app


@pytest.fixture
def planfile_env(tmp_path, monkeypatch):
    """Create a temporary Planfile instance and patch get_planfile to return it."""
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr("planfile.api.server.get_planfile", lambda: pf)
    monkeypatch.setattr("planfile.server_common.get_planfile", lambda: pf)
    return pf


def test_voice_digest_empty_sprint(planfile_env):
    """Empty sprint produces zero counts and clean TTS summary."""
    client = TestClient(app)
    response = client.get("/api/voice-digest?sprint=current")
    assert response.status_code == 200
    data = response.json()
    assert data["sprint"] == "current"
    assert data["total_tickets"] == 0
    assert data["done_tickets"] == 0
    assert data["in_progress_tickets"] == 0
    assert data["blocked_tickets"] == 0
    assert data["todo_tickets"] == 0
    assert "empty with 0 tickets" in data["summary_text"]
    assert "currently has no active tickets" in data["tts_text"]
    assert "no-store" in response.headers.get("cache-control", "").lower()


def test_voice_digest_empty_sprint_polish(planfile_env):
    """Empty sprint produces Polish TTS message when lang=pl."""
    client = TestClient(app)
    response = client.get("/api/voice-digest?sprint=current&lang=pl")
    assert response.status_code == 200
    data = response.json()
    assert data["sprint"] == "current"
    assert data["total_tickets"] == 0
    assert "pusty" in data["summary_text"]
    assert "nie zawiera obecnie żadnych zadań" in data["tts_text"]


def test_voice_digest_populated_sprint(planfile_env):
    """Populated sprint computes accurate counts and natural-language overview."""
    # 2 done, 1 in-progress, 1 blocked, 1 todo
    planfile_env.create_ticket(name="Task 1", sprint="sprint-1", status="done")
    planfile_env.create_ticket(name="Task 2", sprint="sprint-1", status="completed")
    planfile_env.create_ticket(name="Task 3", sprint="sprint-1", status="in_progress")
    planfile_env.create_ticket(name="Task 4", sprint="sprint-1", status="blocked")
    planfile_env.create_ticket(name="Task 5", sprint="sprint-1", status="open")

    client = TestClient(app)
    response = client.get("/api/voice-digest?sprint=sprint-1")
    assert response.status_code == 200
    data = response.json()
    assert data["sprint"] == "sprint-1"
    assert data["total_tickets"] == 5
    assert data["done_tickets"] == 2
    assert data["in_progress_tickets"] == 1
    assert data["blocked_tickets"] == 1
    assert data["todo_tickets"] == 1

    assert "Sprint 'sprint-1': 2/5 done (40%), 1 in progress, 1 blocked, 1 to do." == data["summary_text"]
    assert "Sprint sprint-1 digest: 5 total tickets." in data["tts_text"]
    assert "2 completed, 1 in progress, 1 to do." in data["tts_text"]
    assert "Notice: 1 ticket is blocked." in data["tts_text"]


def test_voice_digest_populated_sprint_polish(planfile_env):
    """Populated sprint computes Polish natural-language overview."""
    planfile_env.create_ticket(name="Task A", sprint="sprint-2", status="done")
    planfile_env.create_ticket(name="Task B", sprint="sprint-2", status="blocked")
    planfile_env.create_ticket(name="Task C", sprint="sprint-2", status="blocked")

    client = TestClient(app)
    response = client.get("/api/voice-digest?sprint=sprint-2&lang=pl")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tickets"] == 3
    assert data["done_tickets"] == 1
    assert data["blocked_tickets"] == 2
    assert "Podsumowanie sprintu sprint-2: łącznie 3 zgłoszeń." in data["tts_text"]
    assert "Uwaga: 2 zgłoszeń jest zablokowanych." in data["tts_text"]


def test_voice_digest_all_tickets_complete(planfile_env):
    """All tickets complete produces completion praise in TTS text."""
    planfile_env.create_ticket(name="Done 1", sprint="release-1", status="done")
    planfile_env.create_ticket(name="Done 2", sprint="release-1", status="done")

    client = TestClient(app)
    response = client.get("/api/voice-digest?sprint=release-1")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tickets"] == 2
    assert data["done_tickets"] == 2
    assert "All tickets in this sprint are complete." in data["tts_text"]


def test_voice_digest_invalid_sprint_name(planfile_env):
    """Invalid sprint name with characters violating pattern is rejected with 422."""
    client = TestClient(app)
    response = client.get("/api/voice-digest?sprint=invalid%20sprint%20name!")
    assert response.status_code == 422
