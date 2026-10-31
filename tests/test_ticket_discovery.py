"""Public indexed discovery preserves scope, freshness and bounded work."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from planfile import Planfile
from planfile.api import server
from planfile.core.models import Ticket
from planfile.core.sqlite_index import SQLiteTicketIndex


@pytest.fixture
def discovery(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    records = []
    for number, status, state, repository in [
        (1, "open", "ready", "semcod/planfile"),
        (2, "open", "ready", "semcod/planfile"),
        (3, "done", "done", "semcod/planfile"),
        (4, "blocked", "waiting_dependency", "semcod/planfile"),
        (5, "failed", "failed", "semcod/planfile"),
        (6, "open", "ready", "other/project"),
        (7, "canceled", "canceled", "semcod/planfile"),
    ]:
        records.append(Ticket(
            id=f"PLF-{number}", name=f"Work {number}", status=status,
            execution={"queue": "coding-agent", "state": state},
            inputs={"api_body": {"source": {"repository": repository, "issue": 244}}},
            description="Retained detail", outputs={"notes": ["Retained evidence"]},
        ))
    for sprint, tickets in [
        ("current", [t for t in records if t.status.value not in ("done", "canceled")]),
        ("history", [t for t in records if t.status.value in ("done", "canceled")]),
    ]:
        pf.store._write_yaml_atomic(pf.store._sprint_file(sprint), {
            "sprint": {"id": sprint, "tickets": {
                t.id: t.model_dump(mode="json", exclude_none=True) for t in tickets
            }},
        })
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    return pf, TestClient(server.app)


def test_sdk_and_http_pages_include_explicit_history_without_widening_scope(discovery):
    pf, client = discovery
    expected = pf.discover_tickets(mode="issue", repository="SEMCOD/Planfile", issue=244)
    response = client.get("/tickets/discovery", params={
        "mode": "issue", "repository": "https://github.com/semcod/planfile.git", "issue": 244,
    })
    assert response.status_code == 200, response.text
    assert response.json() == expected
    assert "ticket.discovery.current_scoped_pages" in client.get("/health").json()["capabilities"]
    assert "X-Total-Count" not in response.headers
    assert "no-store" in response.headers["cache-control"]
    assert {row["id"] for row in expected["tickets"]} == {
        "PLF-1", "PLF-2", "PLF-3", "PLF-4", "PLF-5", "PLF-7",
    }
    assert all("inputs" not in row and "outputs" not in row for row in expected["tickets"])
    full = pf.discover_tickets(mode="issue", repository="semcod/planfile", issue=244, view="full")
    assert full["tickets"][0]["description"] == "Retained detail"


@pytest.mark.parametrize("state,ids", [
    ("ready", {"PLF-1", "PLF-2"}), ("waiting_dependency", {"PLF-4"}),
    ("failed", {"PLF-5"}), ("done", set()), ("canceled", set()),
])
def test_queue_state_discovery_keeps_waits_retries_and_terminal_boundaries(discovery, state, ids):
    pf, client = discovery
    paths = list(pf.store._all_sprint_files())
    before = {str(p): p.read_bytes() for p in paths}
    response = client.get("/tickets/discovery", params={
        "mode": "queue", "queue": "coding-agent", "state": state,
        "repository": "semcod/planfile",
    })
    assert response.status_code == 200, response.text
    assert {row["id"] for row in response.json()["tickets"]} == ids
    assert all(row["execution"]["state"] == state for row in response.json()["tickets"])
    assert {str(p): p.read_bytes() for p in paths} == before


def test_keyset_pages_bind_normalized_scope_view_and_generation(discovery):
    pf, client = discovery
    query = {"mode": "issue", "repository": "semcod/planfile", "issue": 244, "limit": 2}
    first = client.get("/tickets/discovery", params=query).json()
    second = client.get("/tickets/discovery", params={**query, "repository": "SEMCOD/Planfile",
                                                     "cursor": first["next_cursor"]}).json()
    third = client.get("/tickets/discovery", params={**query, "cursor": second["next_cursor"]}).json()
    assert third["next_cursor"] is None
    assert len({r["id"] for page in [first, second, third] for r in page["tickets"]}) == 6
    for changes in [{"repository": "other/project"}, {"issue": 245}, {"view": "full"}]:
        response = client.get("/tickets/discovery", params={**query, **changes,
                                                           "cursor": first["next_cursor"]})
        assert response.status_code == 422
    pf.store.update_ticket("PLF-1", name="Changed after the first page")
    pf.store.ensure_ticket_index()
    response = client.get("/tickets/discovery", params={**query, "cursor": first["next_cursor"]})
    assert response.status_code == 409
    assert response.json()["detail"] == "ticket_discovery_cursor_expired"


@pytest.mark.parametrize("query", [
    {}, {"mode": "other"}, {"mode": "issue", "issue": 244},
    {"mode": "issue", "repository": "bad", "issue": 244},
    {"mode": "issue", "repository": "semcod/planfile", "issue": 0},
    {"mode": "queue", "queue": "coding-agent"},
    {"mode": "queue", "queue": " ", "state": "ready"},
    {"mode": "queue", "queue": "coding-agent", "state": "ready", "issue": 244},
    {"mode": "issue", "repository": "semcod/planfile", "issue": 244, "limit": 501},
    {"mode": "issue", "repository": "semcod/planfile", "issue": 244, "cursor": "broken"},
])
def test_invalid_public_discovery_cannot_fall_through_to_ticket_id_lookup(discovery, query):
    _, client = discovery
    assert client.get("/tickets/discovery", params=query).status_code == 422


def test_discovery_never_repairs_or_falls_back_to_authoritative_archive(discovery, monkeypatch):
    pf, client = discovery
    def forbidden(*args, **kwargs):
        pytest.fail("Discovery attempted a global count, archive read or foreground rebuild")
    for name in ["ensure_ticket_index", "list_tickets", "_ticket_index_records", "load_sprint"]:
        monkeypatch.setattr(pf.store, name, forbidden)
    monkeypatch.setattr(SQLiteTicketIndex, "status", forbidden)
    monkeypatch.setattr(SQLiteTicketIndex, "_connect", forbidden)
    query = {"mode": "queue", "queue": "coding-agent", "state": "ready"}
    assert client.get("/tickets/discovery", params=query).status_code == 200
    path = pf.store._sprint_file("current")
    path.write_bytes(path.read_bytes() + b"\n")
    stale = client.get("/tickets/discovery", params=query)
    assert stale.status_code == 503 and stale.headers["Retry-After"] == "2"
    monkeypatch.setattr(pf.store, "ticket_index_enabled", lambda: False)
    assert client.get("/tickets/discovery", params=query).status_code == 503


def test_concurrent_generation_change_never_returns_a_discovery_success(discovery, monkeypatch):
    pf, client = discovery
    original = SQLiteTicketIndex.queue_page
    def change_after_read(index, *args, **kwargs):
        rows = original(index, *args, **kwargs)
        path = pf.store._sprint_file("current")
        path.write_bytes(path.read_bytes() + b"\n")
        return rows
    monkeypatch.setattr(SQLiteTicketIndex, "queue_page", change_after_read)
    response = client.get("/tickets/discovery", params={
        "mode": "queue", "queue": "coding-agent", "state": "ready",
    })
    assert response.status_code == 503
    assert response.json()["detail"] == "ticket_index_changed_during_discovery"


def test_discovery_materializes_only_summary_page_plus_one(discovery, monkeypatch):
    pf, _ = discovery
    calls = []
    connect = SQLiteTicketIndex._connect_routing
    def traced(index):
        connection = connect(index)
        connection.set_trace_callback(calls.append)
        return connection
    monkeypatch.setattr(SQLiteTicketIndex, "_connect_routing", traced)
    page = pf.discover_tickets(mode="issue", repository="semcod/planfile", issue=244, limit=2)
    assert len(page["tickets"]) == 2 and page["next_cursor"]
    assert len([sql for sql in calls if "SELECT summary_json FROM tickets" in sql]) == 3
    assert not any("COUNT(" in sql.upper() or "OFFSET" in sql.upper()
                   or "SELECT ticket_json" in sql for sql in calls)


def test_sdk_rejects_bool_issue_or_limit(discovery):
    pf, _ = discovery
    for query in [{"issue": True}, {"issue": 244, "limit": True}]:
        with pytest.raises(ValueError):
            pf.discover_tickets(mode="issue", repository="semcod/planfile", **query)


def test_legacy_projection_is_not_upgraded_by_discovery(discovery, monkeypatch):
    pf, client = discovery
    index = pf.store._sqlite_ticket_index()
    with index._connection() as connection:
        connection.execute("DROP TABLE ticket_routes")
        connection.execute("DELETE FROM meta WHERE key='routes_version'")
    def forbidden(*args, **kwargs):
        pytest.fail("A discovery GET invoked the writable index connection")
    monkeypatch.setattr(SQLiteTicketIndex, "_connect", forbidden)
    response = client.get("/tickets/discovery", params={
        "mode": "queue", "queue": "coding-agent", "state": "ready",
    })
    assert response.status_code == 503
    with sqlite3.connect(index.path) as connection:
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='ticket_routes'").fetchone() is None
        assert connection.execute("SELECT value FROM meta WHERE key='routes_version'").fetchone() is None


def test_index_contention_is_retryable_without_a_write_or_fallback(discovery, monkeypatch):
    _, client = discovery
    def locked(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(SQLiteTicketIndex, "_connect_routing", locked)
    response = client.get("/tickets/discovery", params={
        "mode": "queue", "queue": "coding-agent", "state": "ready",
    })
    assert response.status_code == 503 and response.headers["Retry-After"] == "2"


def test_index_page_keeps_payloads_after_a_concurrent_delete(tmp_path, monkeypatch):
    index = SQLiteTicketIndex(tmp_path / "index.sqlite3")
    def record(number):
        ticket = Ticket(id=f"PLF-{number}", name=f"Before {number}",
                        execution={"queue": "coding-agent", "state": "ready"})
        return Planfile(str(tmp_path / "project")).store._ticket_index_record(ticket, "current", number)
    index.rebuild([record(1), record(2)], ("before",))
    connect = index._connect
    submitted = False
    def trace(sql):
        nonlocal submitted
        if not submitted and sql.startswith("SELECT ticket_json FROM tickets"):
            submitted = True
            index.apply(deletes=["PLF-2"], upserts=[], signature=("after",))
    def traced():
        connection = connect()
        connection.set_trace_callback(trace)
        return connection
    monkeypatch.setattr(index, "_connect", traced)
    assert [r["id"] for r in index.queue_page("coding-agent", "ready")] == ["PLF-1", "PLF-2"]
    assert submitted and index.get_ticket("PLF-2") is None
