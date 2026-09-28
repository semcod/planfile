from __future__ import annotations

import pytest
import yaml

from planfile import Planfile
from planfile.core.store import TicketUpdatedAtConflictError


def fixture_store(tmp_path, *, sharded=False, indexed=False, current=False, locator=True):
    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    pf.store._write_config(config)
    ticket = pf.create_ticket(name="Original", sprint="history-2026-09-26")
    raw = ticket.model_dump(mode="json", exclude_none=True)
    for sprint, stamp in [
        ("history-2026-09-26", "2026-09-26T12:00:00Z"),
        ("history-2026-09-27", "2026-09-27T12:00:00Z"),
    ]:
        record = dict(raw, sprint=sprint, updated_at=stamp, name=sprint)
        pf.store._write_yaml_atomic(
            pf.store._sprint_file(sprint),
            {"sprint": {"id": sprint, "tickets": {ticket.id: record}}},
        )
    if current:
        pf.store._write_yaml_atomic(
            pf.store._sprint_file("current"),
            {
                "sprint": {
                    "id": "current",
                    "tickets": {ticket.id: dict(raw, sprint="current", name="current")},
                }
            },
        )
    if locator:
        pf.store._record_history_locations_unlocked({ticket.id: "history-2026-09-27"})
    if sharded:
        pf.store.migrate_to_sharded_yaml()
    if indexed:
        pf.store.configure_ticket_index(True)
    return pf.store, ticket.id


def read_record(store, sprint, ticket_id):
    if store._uses_sharded_storage():
        return store._sharded_storage().get_ticket(sprint, ticket_id)
    return yaml.safe_load(store._sprint_file(sprint).read_text())["sprint"]["tickets"].get(
        ticket_id
    )


@pytest.mark.parametrize("sharded", [False, True])
@pytest.mark.parametrize("indexed", [False, True])
@pytest.mark.parametrize(
    "current,locator,selected",
    [
        (False, True, "history-2026-09-27"),
        (True, True, "current"),
        (False, False, "history-2026-09-26"),
    ],
)
def test_observed_record_is_updated_without_touching_siblings(
    tmp_path, sharded, indexed, current, locator, selected
):
    store, ticket_id = fixture_store(
        tmp_path, sharded=sharded, indexed=indexed, current=current, locator=locator
    )
    siblings = {
        s: read_record(store, s, ticket_id)
        for s in store._all_sprint_ids()
        if s != selected and read_record(store, s, ticket_id) is not None
    }
    observed = store.get_ticket(ticket_id)
    assert observed.name == selected
    revision = observed.model_dump(mode="json")["updated_at"]
    updated = store.update_ticket(
        ticket_id, description="Reconciled mapping", expected_updated_at=revision
    )
    assert updated.description == "Reconciled mapping"
    assert read_record(store, selected, ticket_id)["description"] == "Reconciled mapping"
    assert store.get_ticket(ticket_id).description == "Reconciled mapping"
    for sprint, before in siblings.items():
        assert read_record(store, sprint, ticket_id) == before
    after = read_record(store, selected, ticket_id)
    with pytest.raises(TicketUpdatedAtConflictError, match="ticket_updated_at_precondition_failed"):
        store.update_ticket(ticket_id, description="Stale write", expected_updated_at=revision)
    assert read_record(store, selected, ticket_id) == after


@pytest.mark.parametrize("sharded", [False, True])
@pytest.mark.parametrize("indexed", [False, True])
def test_missing_locator_target_falls_back_without_hiding_record(tmp_path, sharded, indexed):
    store, ticket_id = fixture_store(tmp_path, sharded=sharded)
    store._record_history_locations_unlocked({ticket_id: "history-missing"})
    if indexed:
        store.configure_ticket_index(True)
    observed = store.get_ticket(ticket_id)
    assert observed.name == "history-2026-09-26"
    updated = store.update_ticket(
        ticket_id,
        description="Fallback",
        expected_updated_at=observed.model_dump(mode="json")["updated_at"],
    )
    assert updated.description == "Fallback"


@pytest.mark.parametrize("sharded", [False, True])
def test_locator_change_invalidates_index_and_rejects_stale_observation(tmp_path, sharded):
    store, ticket_id = fixture_store(tmp_path, sharded=sharded, indexed=True)
    observed = store.get_ticket(ticket_id)
    # Simulate a separate writer changing only the durable locator.
    other = Planfile(str(tmp_path)).store
    other._record_history_locations_unlocked({ticket_id: "history-2026-09-26"})
    assert store.get_ticket(ticket_id).name == "history-2026-09-26"
    before = {s: read_record(store, s, ticket_id) for s in store._all_sprint_ids()}
    with pytest.raises(TicketUpdatedAtConflictError):
        store.update_ticket(
            ticket_id,
            description="Wrong record",
            expected_updated_at=observed.model_dump(mode="json")["updated_at"],
        )
    assert {s: read_record(store, s, ticket_id) for s in store._all_sprint_ids()} == before
