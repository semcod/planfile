from __future__ import annotations

import pytest

from planfile import Planfile


def test_stale_full_sprint_save_does_not_erase_a_concurrently_created_ticket(tmp_path):
    pf = Planfile(str(tmp_path))
    stale = pf.store.load_sprint("current")

    created = pf.create_ticket(name="must survive a stale bulk save")
    pf.store.save_sprint("current", stale)

    assert pf.get_ticket(created.id) is not None


def test_stale_full_sprint_save_does_not_revert_a_newer_ticket_update(tmp_path):
    pf = Planfile(str(tmp_path))
    created = pf.create_ticket(name="newer lifecycle wins")
    stale = pf.store.load_sprint("current")

    pf.complete_ticket(created.id, note="completed by concurrent writer")
    stale["tickets"][created.id]["priority"] = "high"
    pf.store.save_sprint("current", stale)

    current = pf.get_ticket(created.id)
    assert current is not None
    assert getattr(current.status, "value", current.status) == "done"
    assert current.outputs.notes == ["completed by concurrent writer"]


def test_backlog_save_preserves_tickets_created_after_snapshot(tmp_path):
    pf = Planfile(str(tmp_path))
    stale = pf.store.load_backlog()
    created = pf.create_ticket(name="backlog concurrent ticket", sprint="backlog")

    pf.store.save_backlog(stale)

    assert pf.get_ticket(created.id) is not None


def test_move_ticket_persists_destination_and_history(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Move atomically", sprint="current")

    assert pf.store.move_ticket(ticket.id, "audit-sprint") is True

    moved = pf.get_ticket(ticket.id)
    assert moved is not None
    assert moved.sprint == "audit-sprint"
    assert moved.history[-1]["reason"] == "move_ticket"
    assert pf.store.list_tickets(sprint="current") == []
    assert [item.id for item in pf.store.list_tickets(sprint="audit-sprint")] == [ticket.id]


def test_sprint_path_traversal_is_rejected(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Stay contained")

    with pytest.raises(ValueError, match="invalid_sprint_id"):
        pf.store.move_ticket(ticket.id, "../../outside")

    assert not (tmp_path / "outside.yaml").exists()
