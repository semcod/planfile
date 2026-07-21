from __future__ import annotations

from planfile.sync.onedev import OneDevBackend


class FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload
        self.content = b"" if payload is None else b"json"
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, issues):
        self.auth = None
        self.headers = {}
        self.issues = list(issues)
        self.calls = []

    def request(self, method, url, json=None, params=None, timeout=None):
        self.calls.append((method, url, json, params))
        if url.endswith("/~api/projects"):
            return FakeResponse(
                [
                    {"id": 1, "name": "subactor", "parentId": None},
                    {"id": 10, "name": "doctor-agent", "parentId": 1},
                ]
            )
        if url.endswith("/~api/issues") and method == "GET":
            return FakeResponse(self.issues)
        if url.endswith("/~api/issues") and method == "POST":
            issue = {
                "id": 12,
                "number": 3,
                "projectId": 10,
                "state": "Open",
                "title": json["title"],
                "description": json["description"],
                "fields": [],
                "lastActivity": {"date": "2026-07-21T10:00:00Z"},
            }
            self.issues.append(issue)
            return FakeResponse(12)
        if "/~api/issues/" in url and method == "GET":
            issue_id = int(url.rsplit("/", 1)[1])
            return FakeResponse(next(issue for issue in self.issues if issue["id"] == issue_id))
        if "/~api/issues/" in url and method == "POST":
            return FakeResponse()
        raise AssertionError((method, url, json, params, timeout))


def issue(description="<!-- ifuri-doctor:fingerprint=doctor:abc -->\nevidence"):
    return {
        "id": 11,
        "number": 2,
        "projectId": 10,
        "state": "Open",
        "title": "Doctor finding",
        "description": description,
        "fields": [
            {"name": "Priority", "value": "Major"},
            {"name": "Type", "value": "Bug"},
            {"name": "Assignees", "value": "worker"},
        ],
        "lastActivity": {"date": "2026-07-21T10:00:00Z"},
    }


def backend(session):
    return OneDevBackend(
        url="http://onedev:6610",
        project="subactor/doctor-agent",
        username="agent",
        password="secret",
        session=session,
        publish_to=["github"],
    )


def test_lists_full_ticket_state_and_preserves_doctor_fingerprint():
    session = FakeSession([issue()])
    client = backend(session)

    tickets = client.list_tickets()

    assert len(tickets) == 1
    assert tickets[0].id == "11"
    assert tickets[0].name == "Doctor finding"
    assert tickets[0].description.endswith("evidence")
    assert tickets[0].status == "open"
    assert tickets[0].assignee == "worker"
    assert tickets[0].metadata["deduplication_key"] == "doctor:abc"
    assert client.publish_to == ["github"]
    assert session.auth == ("agent", "secret")


def test_create_is_idempotent_by_fingerprint_marker():
    session = FakeSession([issue("<!-- ifuri-doctor:fingerprint=doctor:abc -->\nevidence")])
    client = backend(session)

    reused = client.create_ticket(
        {"name": "same", "description": "evidence", "metadata": {"fingerprint": "doctor:abc"}}
    )
    created = client.create_ticket(
        {"name": "new", "description": "new evidence", "metadata": {"fingerprint": "doctor:new"}}
    )

    assert reused.id == "11"
    assert created.id == "12"
    create_calls = [
        call for call in session.calls if call[0] == "POST" and call[1].endswith("/~api/issues")
    ]
    assert len(create_calls) == 1
    assert "<!-- planfile:deduplication-key=doctor:new -->" in create_calls[0][2]["description"]


def test_public_ensure_contract_reports_created_and_reused():
    session = FakeSession([issue()])
    client = backend(session)

    project = client.ensure_project()
    reused, reused_created = client.ensure_ticket(
        {"name": "same", "description": "evidence", "metadata": {"fingerprint": "doctor:abc"}}
    )
    created, was_created = client.ensure_ticket(
        {"name": "new", "description": "evidence", "metadata": {"fingerprint": "doctor:new"}}
    )

    assert project["id"] == 10
    assert reused.id == "11"
    assert reused_created is False
    assert created.id == "12"
    assert was_created is True


def test_update_uses_onedev_state_transition_endpoint():
    session = FakeSession([issue()])
    client = backend(session)

    client.update_ticket("11", status="done")

    transition = next(call for call in session.calls if call[1].endswith("/11/state-transitions"))
    assert transition[2]["state"] == "Closed"
