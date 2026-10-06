"""Regression test for ticket-126 and ticket-193: entries without an explicit id field."""

import yaml

from planfile import Planfile
from planfile.core.store import Store
from planfile.core.store_tickets import TicketStoreMixin


class _Mixed(TicketStoreMixin):
    pass


def test_entry_missing_id_falls_back_to_the_dict_key():
    store = _Mixed()
    sprint_data = {
        "tickets": {
            "GITHUB-11": {
                "name": "No title",
                "status": "done",
            },
            "PLF-002": {
                "id": "PLF-002",
                "name": "Has its own id",
                "status": "open",
            },
        }
    }

    tickets = store._tickets_from_sprint_data(sprint_data)

    ids = {t.id for t in tickets}
    assert ids == {"GITHUB-11", "PLF-002"}


def test_non_dict_entry_is_skipped_instead_of_raising():
    store = _Mixed()
    sprint_data = {"tickets": {"bogus": "not-a-dict", "PLF-003": {"id": "PLF-003", "name": "ok"}}}

    tickets = store._tickets_from_sprint_data(sprint_data)

    assert [t.id for t in tickets] == ["PLF-003"]


def test_store_get_ticket_and_records_fallback_to_dict_key(tmp_path):
    store = Store(tmp_path)
    store.init()

    # Write legacy tickets without explicit "id" in backlog.yaml
    backlog_path = tmp_path / ".planfile" / "sprints" / "backlog.yaml"
    backlog_data = {
        "sprint": {
            "id": "backlog",
            "name": "Backlog",
            "tickets": {
                "GITHUB-14": {
                    "name": "Legacy imported ticket",
                    "status": "open",
                    "description": "Legacy format",
                }
            },
        }
    }
    backlog_path.write_text(yaml.safe_dump(backlog_data), encoding="utf-8")

    # 1. store.get_ticket returns the ticket with id set to GITHUB-14
    ticket = store.get_ticket("GITHUB-14")
    assert ticket is not None
    assert ticket.id == "GITHUB-14"
    assert ticket.name == "Legacy imported ticket"

    # 2. ticket_records yields the ticket with id set
    records = list(store.ticket_records(sprint="all"))
    gh_record = next((r for r in records if r.get("id") == "GITHUB-14"), None)
    assert gh_record is not None
    assert gh_record["id"] == "GITHUB-14"

    # 3. High-level Planfile API and SQLite index read it cleanly
    pf = Planfile(str(tmp_path))
    pf_ticket = pf.get_ticket("GITHUB-14")
    assert pf_ticket is not None
    assert pf_ticket.id == "GITHUB-14"
