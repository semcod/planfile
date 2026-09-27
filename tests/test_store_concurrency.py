from __future__ import annotations

import pytest
import yaml

from planfile import Planfile


def _envelope_fixture(tmp_path, sprint, sharded):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Sync target", sprint=sprint)
    path = pf.store._sprint_file(sprint)
    data = yaml.safe_load(path.read_text())
    extensions = {"schema": "custom-plan/v1", "tasks": [{"id": "external", "status": "todo"}]}
    data.update(extensions)
    pf.store._write_yaml_atomic(path, data, allow_unicode=True)
    if sharded:
        pf.store.migrate_to_sharded_yaml()
        path = pf.store._sharded_storage().metadata_path(sprint)
    return pf, ticket, path, extensions


@pytest.mark.parametrize("sprint", ["current", "backlog", "custom"])
@pytest.mark.parametrize("sharded", [False, True])
def test_stale_save_preserves_envelope_and_concurrent_ticket(tmp_path, sprint, sharded):
    pf, ticket, path, extensions = _envelope_fixture(tmp_path, sprint, sharded)
    # Physical migration must retain fields outside the typed sprint too.
    assert yaml.safe_load(path.read_text())["tasks"] == extensions["tasks"]
    stale = pf.store.load_sprint(sprint)
    other = Planfile(str(tmp_path))
    created = other.create_ticket(name="Concurrent ticket", sprint=sprint)
    fresh = yaml.safe_load(path.read_text())
    fresh["tasks"] = [{"id": "external", "status": "done"}]
    other.store._write_yaml_atomic(path, fresh, allow_unicode=True)
    pf.store.save_sprint(sprint, stale)

    saved = yaml.safe_load(path.read_text())
    assert saved["schema"] == extensions["schema"]
    assert saved["tasks"] == fresh["tasks"]
    assert "tasks" not in saved["sprint"]
    reloaded = Planfile(str(tmp_path))
    assert {t.id for t in reloaded.list_tickets(sprint=sprint)} == {ticket.id, created.id}


@pytest.mark.parametrize("sharded", [False, True])
def test_wrapped_save_does_not_revert_fresh_envelope_fields(tmp_path, sharded):
    pf, _, path, _ = _envelope_fixture(tmp_path, "backlog", sharded)
    stale = yaml.safe_load(path.read_text())
    stale["sprint"] = pf.store.load_backlog()
    stale["new_extension"] = {"enabled": True}
    fresh = yaml.safe_load(path.read_text())
    fresh["tasks"] = [{"id": "newer", "status": "todo"}]
    pf.store._write_yaml_atomic(path, fresh, allow_unicode=True)

    pf.store.save_backlog(stale)

    saved = yaml.safe_load(path.read_text())
    assert saved["tasks"] == fresh["tasks"]
    assert saved["schema"] == stale["schema"]
    assert saved["new_extension"] == {"enabled": True}


@pytest.mark.parametrize("sharded", [False, True])
def test_outbound_sync_keeps_envelope_and_issue_mapping(tmp_path, sharded):
    from types import SimpleNamespace

    from planfile.sync.operations import sync_to_external

    pf, ticket, path, extensions = _envelope_fixture(tmp_path, "current", sharded)

    class Backend:
        config = {"repo": "owner/repo"}

        def create_ticket(self, payload):
            # Another writer adds a ticket while the request is in flight.
            Planfile(str(tmp_path)).create_ticket(name="Unrelated writer")
            return SimpleNamespace(id="42", url="https://github.com/owner/repo/issues/42",
                                   key="owner/repo#42")

    result = sync_to_external(Backend(), [(ticket.id, ticket.model_dump(mode="json"))],
                              False, pf.store, "github")

    assert result.succeeded == (ticket.id,)
    saved = yaml.safe_load(path.read_text())
    assert {key: saved[key] for key in extensions} == extensions
    reloaded = Planfile(str(tmp_path))
    assert reloaded.get_ticket(ticket.id).sync["github"]["id"] == "42"
    assert {t.name for t in reloaded.list_tickets()} == {"Sync target", "Unrelated writer"}


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
