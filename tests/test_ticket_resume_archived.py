from __future__ import annotations

import json
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from planfile import Planfile
from planfile.core.fastio import mirror_path
from planfile.core.models import TicketExecution
from planfile.core.sharded_yaml import ShardedYamlStorage
from planfile.core.store import ImmutableTerminalReopenError, Store


@pytest.fixture(params=["single-yaml", "sharded-yaml"])
def pf(tmp_path: Path, request):
    planfile = Planfile(str(tmp_path))
    if request.param == "sharded-yaml":
        planfile.store.migrate_to_sharded_yaml(shard_size=10)
    return planfile


def seed_history_locations(store, locations):
    # Reproduce legacy archive metadata independently of move_ticket's behavior.
    with store.mutation_lock():
        store._write_yaml_atomic(
            store._history_locations_path,
            {"schema": "planfile.history-locations/v1", "tickets": locations},
        )
    assert_history_locations(store, locations)


def assert_history_locations(store, expected):
    path = store._history_locations_path
    durable = yaml.safe_load(path.read_text())
    assert durable["tickets"] == expected
    mirror = json.loads(mirror_path(path).read_text())
    assert mirror["data"] == durable
    assert mirror["yaml_mtime_ns"] == path.stat().st_mtime_ns
    assert store._history_locations() == expected
    assert Store(store.project_dir)._history_locations() == expected
    # Match the canonical owner check using durable YAML, without Store lookup.
    for ticket_id, owner in expected.items():
        assert owner.startswith(("history-", "archive-"))
        paths = (
            list((store._sprints_dir / f"{owner}.shards").glob("tickets-*.yaml"))
            if store._uses_sharded_storage()
            else [store._sprint_file(owner)]
        )
        tickets = {}
        for owner_path in paths:
            data = yaml.safe_load(owner_path.read_text())
            tickets.update(data.get("sprint", data)["tickets"])
        assert ticket_id in tickets


def test_resume_archived_unfinished_ticket_restores_current_runnability(pf):
    old = datetime.now(timezone.utc) - timedelta(days=2)

    # Create an unfinished ticket that failed/blocked and was archived into history
    ticket = pf.create_ticket(
        name="Recoverable unfinished task",
        status="blocked",
        execution=TicketExecution(state="blocked", queue="default"),
    )
    history_sprint = f"history-{old:%Y-%m-%d}"
    moved = pf.store.move_ticket(ticket.id, history_sprint)
    assert moved is True
    seed_history_locations(pf.store, {ticket.id: history_sprint})

    # While archived, ticket is NOT in current sprint or runnable report
    current_tickets = pf.list_tickets(sprint="current")
    assert ticket.id not in [t.id for t in current_tickets]
    runnable = pf.runnable_report(sprint="current")
    assert ticket.id not in runnable["servable"]

    # Resume the ticket
    resumed = pf.resume_ticket(ticket.id, note="Unblocked after dependency fix")
    assert resumed is not None
    assert resumed.id == ticket.id
    assert resumed.status.value == "open"
    assert resumed.execution.state == "ready"
    assert resumed.sprint == "current"
    assert_history_locations(pf.store, {})

    # Ticket is now admitted in current sprint and runnable report
    current_tickets_after = pf.list_tickets(sprint="current")
    assert ticket.id in [t.id for t in current_tickets_after]
    runnable_after = pf.runnable_report(sprint="current")
    assert ticket.id in runnable_after["servable"]
    next_up = pf.next_ticket(sprint="current")
    assert next_up is not None
    assert next_up.id == ticket.id


def test_ready_ticket_on_archived_ticket_restores_to_current(pf):
    ticket = pf.create_ticket(
        name="Task to ready",
        status="open",
        execution=TicketExecution(state="failed", queue="default"),
    )
    # Move to history
    pf.store.move_ticket(ticket.id, "history-2026-10-01")
    seed_history_locations(pf.store, {ticket.id: "history-2026-10-01"})
    assert ticket.id not in [t.id for t in pf.list_tickets(sprint="current")]

    # ready_ticket restores it to current
    ready = pf.ready_ticket(ticket.id)
    assert ready is not None
    assert ready.status.value == "open"
    assert ready.execution.state == "ready"
    assert ready.sprint == "current"
    assert_history_locations(pf.store, {})
    assert ticket.id in [t.id for t in pf.list_tickets(sprint="current")]


def test_resume_rejects_completed_or_canceled_ticket(pf):
    done_ticket = pf.create_ticket(name="Done task", status="done")
    canceled_ticket = pf.create_ticket(name="Canceled task", status="canceled")

    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.resume_ticket(done_ticket.id)

    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.resume_ticket(canceled_ticket.id)

    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.ready_ticket(done_ticket.id)

    owner = "history-2026-10-01"
    for ticket in (done_ticket, canceled_ticket):
        pf.store.move_ticket(ticket.id, owner)
    locations = {done_ticket.id: owner, canceled_ticket.id: owner}
    seed_history_locations(pf.store, locations)
    for ticket in (done_ticket, canceled_ticket):
        for restore in (pf.resume_ticket, pf.ready_ticket):
            with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
                restore(ticket.id)
    assert_history_locations(pf.store, locations)


def test_cli_ticket_resume_command(pf, tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner

    from planfile.cli.commands import app

    runner = CliRunner()
    ticket = pf.create_ticket(
        name="CLI Resumed task",
        status="open",
        execution=TicketExecution(state="failed", queue="default"),
    )
    pf.store.move_ticket(ticket.id, "history-2026-10-01")
    seed_history_locations(pf.store, {ticket.id: "history-2026-10-01"})

    # Change working directory in test runner
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["ticket", "resume", ticket.id, "-n", "resumed via CLI"])
    assert result.exit_code == 0
    assert "Resumed" in result.output

    reloaded = pf.get_ticket(ticket.id)
    assert reloaded.sprint == "current"
    assert reloaded.execution.state == "ready"
    assert_history_locations(pf.store, {})


def test_resume_archived_unfinished_ticket_sharded_storage(tmp_path: Path):
    pf = Planfile(str(tmp_path))
    pf.store.migrate_to_sharded_yaml(shard_size=10)

    ticket = pf.create_ticket(
        name="Sharded recoverable task",
        status="blocked",
        execution=TicketExecution(state="blocked", queue="default"),
    )
    pf.store.move_ticket(ticket.id, "history-2026-10-02")
    assert ticket.id not in [t.id for t in pf.list_tickets(sprint="current")]

    resumed = pf.resume_ticket(ticket.id)
    assert resumed is not None
    assert resumed.sprint == "current"
    assert resumed.status.value == "open"
    assert resumed.execution.state == "ready"
    assert ticket.id in [t.id for t in pf.list_tickets(sprint="current")]
    runnable = pf.runnable_report(sprint="current")
    assert ticket.id in runnable["servable"]


@pytest.mark.parametrize("indexed", [False, True])
def test_history_locations_moves_preserve_unrelated_owner_and_cache(pf, monkeypatch, indexed):
    store = pf.store
    other = pf.create_ticket(name="Stay archived")
    ticket = pf.create_ticket(name="Move between owners")
    store.move_ticket(other.id, "history-2026-09-30")
    seed_history_locations(store, {other.id: "history-2026-09-30"})
    if indexed:
        store.configure_ticket_index(True)
    observer = Store(store.project_dir)
    assert observer._history_locations() == {other.id: "history-2026-09-30"}
    original_lock = store.mutation_lock
    original_writer = store._write_yaml_atomic
    locked = False
    locator_writes = 0

    @contextmanager
    def tracking_lock(**kwargs):
        nonlocal locked
        with original_lock(**kwargs):
            locked = True
            try:
                yield
            finally:
                locked = False

    def tracking_writer(path, data, **kwargs):
        nonlocal locator_writes
        if path == store._history_locations_path:
            assert locked
            locator_writes += 1
        return original_writer(path, data, **kwargs)

    monkeypatch.setattr(store, "mutation_lock", tracking_lock)
    monkeypatch.setattr(store, "_write_yaml_atomic", tracking_writer)
    for destination in ("history-2026-10-01", "archive-2026-10-02", "current"):
        # Warm model and YAML caches before each relocation.
        observer.list_tickets(sprint="all")
        store.list_tickets(sprint="all")
        store._cached_ticket_index_signature()
        assert store.move_ticket(ticket.id, destination)
        expected = {other.id: "history-2026-09-30"}
        if destination != "current":
            expected[ticket.id] = destination
        assert store._ticket_index_signature_cache is None
        assert_history_locations(store, expected)
        assert observer._history_locations() == expected
        assert observer.get_ticket(ticket.id).sprint == destination
        assert store.get_ticket(ticket.id).sprint == destination
        if indexed:
            assert store.ticket_index_status()["current"]
    assert locator_writes == 3


@pytest.mark.parametrize("destination", ["current", "history-2026-10-03"])
@pytest.mark.parametrize("failure", ["source", "locator"])
@pytest.mark.parametrize("after_write", [False, True])
def test_history_locations_rollback(pf, monkeypatch, destination, failure, after_write):
    store = pf.store
    ticket = pf.create_ticket(name="Rollback me", status="blocked")
    other = pf.create_ticket(name="Keep destination contents")
    source = "history-2026-10-01"
    store.move_ticket(ticket.id, source)
    if destination != "current":
        store.move_ticket(other.id, destination)
    locations = {ticket.id: source}
    if destination != "current":
        locations[other.id] = destination
    seed_history_locations(store, locations)
    source_before = deepcopy(store.load_sprint(source))
    destination_before = deepcopy(store.load_sprint(destination))
    observer = Store(store.project_dir)
    observer.list_tickets(sprint="all")
    observer._history_locations()
    original_writer = store._write_yaml_atomic
    original_delete = ShardedYamlStorage.delete_ticket
    failed = False

    def failing_writer(path, data, **kwargs):
        nonlocal failed
        target = store._history_locations_path if failure == "locator" else store._sprint_file(source)
        if path == target and not failed:
            failed = True
            if after_write:
                original_writer(path, data, **kwargs)
            raise OSError("injected relocation failure")
        return original_writer(path, data, **kwargs)

    def failing_delete(storage, sprint, ticket_id):
        nonlocal failed
        if failure == "source" and sprint == source and not failed:
            failed = True
            if after_write:
                original_delete(storage, sprint, ticket_id)
            raise OSError("injected relocation failure")
        return original_delete(storage, sprint, ticket_id)

    monkeypatch.setattr(store, "_write_yaml_atomic", failing_writer)
    monkeypatch.setattr(ShardedYamlStorage, "delete_ticket", failing_delete)
    with pytest.raises(OSError, match="injected relocation failure"):
        store.move_ticket(ticket.id, destination)
    assert failed
    assert store.load_sprint(source) == source_before
    assert store.load_sprint(destination) == destination_before
    assert_history_locations(store, locations)
    assert observer._history_locations() == locations
    assert observer.get_ticket(ticket.id).sprint == source
    assert Store(store.project_dir).get_ticket(ticket.id).sprint == source
    assert store.move_ticket(ticket.id, destination)
    locations.pop(ticket.id)
    if destination != "current":
        locations[ticket.id] = destination
    assert_history_locations(store, locations)


@pytest.mark.parametrize("after_write", [False, True])
def test_history_locations_new_locator_rollback(pf, monkeypatch, after_write):
    store = pf.store
    ticket = pf.create_ticket(name="First archive move")
    before = deepcopy(store.load_sprint("current"))
    destination = "history-2026-10-04"
    locator = store._history_locations_path
    assert not locator.exists()
    writer = store._write_yaml_atomic
    failed = False

    def fail_first_locator_write(path, data, **kwargs):
        nonlocal failed
        if path == locator and not failed:
            failed = True
            if after_write:
                writer(path, data, **kwargs)
            raise OSError("injected first locator failure")
        return writer(path, data, **kwargs)

    monkeypatch.setattr(store, "_write_yaml_atomic", fail_first_locator_write)
    with pytest.raises(OSError, match="injected first locator failure"):
        store.move_ticket(ticket.id, destination)
    assert failed
    assert not locator.exists()
    assert not mirror_path(locator).exists()
    assert store.load_sprint("current") == before
    assert Store(store.project_dir).get_ticket(ticket.id).sprint == "current"
    assert ticket.id not in [t.id for t in store.list_tickets(sprint=destination)]
    if not store._uses_sharded_storage():
        assert not store._sprint_file(destination).exists()
        assert not mirror_path(store._sprint_file(destination)).exists()
    assert store.move_ticket(ticket.id, destination)
    assert_history_locations(store, {ticket.id: destination})


def test_history_locations_rollback_failure_keeps_destination_copy(pf, monkeypatch):
    store = pf.store
    ticket = pf.create_ticket(name="Preserve the only durable copy")
    destination = "history-2026-10-05"
    if store._uses_sharded_storage():
        storage = store._sharded_storage()
        source_path = storage.shard_path("current", ticket.id)
        destination_path = storage.shard_path(destination, ticket.id)
    else:
        source_path = store._sprint_file("current")
        destination_path = store._sprint_file(destination)
    writer = store._write_yaml_atomic
    rolling_back = False

    def failing_writer(path, data, **kwargs):
        nonlocal rolling_back
        if path == store._history_locations_path:
            rolling_back = True
            raise OSError("locator write failure")
        if rolling_back and path == source_path:
            raise OSError("source restore failure")
        return writer(path, data, **kwargs)

    monkeypatch.setattr(store, "_write_yaml_atomic", failing_writer)
    with pytest.raises(OSError, match="source restore failure"):
        store.move_ticket(ticket.id, destination)
    durable = yaml.safe_load(destination_path.read_text())
    assert durable.get("sprint", durable)["tickets"][ticket.id]["name"] == ticket.name
    assert Store(store.project_dir).get_ticket(ticket.id).sprint == destination
