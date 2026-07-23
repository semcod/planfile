from __future__ import annotations

import json

import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from planfile import Planfile
from planfile.api import server
from planfile.cli.commands import app
from planfile.core.fastio import mirror_path


def _disable_archive(pf: Planfile) -> None:
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    pf.store._write_config(config)


def test_sqlite_index_serves_get_without_reparsing_sprint_files(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket = pf.create_ticket(name="Indexed ticket", priority="high")

    status = pf.store.configure_ticket_index(True)
    assert status["current"] is True
    assert status["tickets"] == 1

    def unexpected_rebuild():
        raise AssertionError("current SQLite get must not reparse sprint files")

    monkeypatch.setattr(pf.store, "_ticket_index_records", unexpected_rebuild)
    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.name == "Indexed ticket"
    assert loaded.priority == "high"


def test_summary_api_pages_and_filters_in_sqlite_without_full_list(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.create_tickets_bulk(
        [
            {
                "name": f"Ticket {number}",
                "priority": "high" if number % 2 else "normal",
            }
            for number in range(10)
        ]
    )
    pf.store.configure_ticket_index(True)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    def unexpected_list(**_filters):
        raise AssertionError("summary page must be served by SQLite")

    monkeypatch.setattr(pf, "list_tickets", unexpected_list)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)
    response = client.get(
        "/tickets",
        params={
            "sprint": "current",
            "priority": "high",
            "offset": 1,
            "limit": 2,
            "view": "summary",
        },
    )

    assert response.status_code == 200
    assert [ticket["name"] for ticket in response.json()] == ["Ticket 3", "Ticket 5"]
    assert response.headers["X-Total-Count"] == "5"
    assert response.headers["X-Result-Count"] == "2"


def test_external_yaml_edit_marks_index_stale_and_self_heals(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Before external edit")
    pf.store.configure_ticket_index(True)
    sprint_file = pf.store._sprint_file("current")
    data = yaml.safe_load(sprint_file.read_text(encoding="utf-8"))
    data["sprint"]["tickets"][ticket.id]["name"] = "After external edit"
    sprint_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(sprint_file).unlink(missing_ok=True)

    assert pf.store.ticket_index_status()["current"] is False
    loaded = pf.get_ticket(ticket.id)
    assert loaded is not None and loaded.name == "After external edit"
    assert pf.store.ticket_index_status()["current"] is True


def test_store_mutation_updates_current_index_incrementally(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Mutable")
    pf.store.configure_ticket_index(True)

    pf.update_ticket(ticket.id, priority="critical")

    assert pf.store.ticket_index_status()["current"] is True
    monkeypatch.setattr(
        pf.store,
        "_ticket_index_records",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected full rebuild")),
    )
    assert pf.get_ticket(ticket.id).priority == "critical"
    assert pf.store.ticket_index_status()["current"] is True


def test_corrupt_sqlite_index_is_discarded_and_rebuilt(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Survives disposable index corruption")
    pf.store.configure_ticket_index(True)
    index_path = pf.store._ticket_index_path
    pf.store._sqlite_ticket_index().reset()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(b"not a sqlite database")

    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.name == "Survives disposable index corruption"
    assert pf.store.ticket_index_status()["current"] is True


def test_evidence_change_updates_index_incrementally(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Evidence indexed")
    pf.store.configure_ticket_index(True)

    projected, recorded = pf.append_ticket_evidence(
        ticket.id,
        idempotency_key="run-1",
        collection="checks",
        evidence={"status": "passed"},
        actor="test",
        reason="verification",
    )

    assert recorded is True and projected is not None
    assert pf.store.ticket_index_status()["current"] is True
    monkeypatch.setattr(
        pf.store,
        "_ticket_index_records",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected full rebuild")),
    )
    loaded = pf.get_ticket(ticket.id)
    assert loaded.outputs.result["checks"][0]["status"] == "passed"
    assert pf.store.ticket_index_status()["current"] is True


def test_sqlite_index_works_with_sharded_yaml(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    created = pf.create_tickets_bulk(
        [{"name": f"Sharded {number}"} for number in range(20)]
    )
    pf.store.migrate_to_sharded_yaml(shard_size=5)
    pf.store.configure_ticket_index(True)

    assert pf.get_ticket(created[-1].id).name == "Sharded 19"
    summaries, total = pf.store.indexed_ticket_summaries(
        sprint="current",
        filters={},
        offset=5,
        limit=3,
    )
    assert total == 20
    assert [item["name"] for item in summaries] == [
        "Sharded 5",
        "Sharded 6",
        "Sharded 7",
    ]


def test_storage_index_cli_lifecycle(tmp_path):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="CLI indexed")
    runner = CliRunner()

    enabled = runner.invoke(
        app,
        ["storage", "index-enable", "--project", str(tmp_path), "--json"],
    )
    status = runner.invoke(
        app,
        ["storage", "index-status", "--project", str(tmp_path), "--json"],
    )
    disabled = runner.invoke(
        app,
        ["storage", "index-disable", "--project", str(tmp_path)],
    )

    assert enabled.exit_code == 0
    assert json.loads(enabled.output)["tickets"] == 1
    assert status.exit_code == 0
    assert json.loads(status.output)["current"] is True
    assert disabled.exit_code == 0
    assert Planfile(str(tmp_path)).store.ticket_index_enabled() is False
