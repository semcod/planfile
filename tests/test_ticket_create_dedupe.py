"""Atomic create-time ticket deduplication."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from planfile import Planfile


@pytest.fixture()
def pf(tmp_path):
    return Planfile(str(tmp_path))


def _incident(pf, occurrence):
    return pf.create_ticket_deduplicated(
        "Incydent zależności: soa://subactor/connector/plesk",
        labels=[
            f"incident:{occurrence}",
            "incident-fingerprint:shared",
            "dedupe:ops-incident:shared",
        ],
    )


def test_parallel_occurrences_with_one_dedupe_key_create_one_ticket(pf):
    """Regression for PLF-3716/3717: occurrence ids differ, cause does not."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: _incident(pf, f"occurrence-{index}"), range(8)))

    assert len({ticket.id for ticket, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    assert len(pf.list_tickets(sprint="all")) == 1


def test_dedupe_label_precedes_unique_incident_occurrence(pf):
    first, created_first = _incident(pf, "one")
    second, created_second = _incident(pf, "two")

    assert created_first is True
    assert created_second is False
    assert second.id == first.id


def test_terminal_ticket_releases_dedupe_key(pf):
    first, _ = _incident(pf, "one")
    pf.store.update_ticket(first.id, status="canceled")
    second, created = _incident(pf, "two")

    assert created is True
    assert second.id != first.id


def test_explicit_api_key_is_materialized_as_label(pf):
    ticket, created = pf.create_ticket_deduplicated("Nightly", dedupe_key="nightly")

    assert created is True
    assert "dedupe:nightly" in ticket.labels


def test_ordinary_tickets_are_not_deduplicated(pf):
    first = pf.create_ticket("Zadanie", labels=["subactor"])
    second = pf.create_ticket("Zadanie", labels=["subactor"])

    assert second.id != first.id


def test_http_reuse_returns_200_without_second_ticket(pf, monkeypatch):
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from planfile.api import server

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    body = {
        "name": "Incydent Plesk",
        "labels": ["incident:one", "dedupe:ops-incident:shared"],
    }

    first = client.post("/tickets", json=body)
    body["labels"][0] = "incident:two"
    second = client.post("/tickets", json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
