"""Regression test for ticket-126: entries without an explicit id field."""

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
