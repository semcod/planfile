"""Offline regressions for GitHub inbound-first reconciliation and lifecycle intent."""

from copy import deepcopy

import pytest
import typer
import yaml

from planfile.cli.groups.sync import core
from planfile.core.store import PlanfileStore, Ticket
from planfile.sync.base import TicketRef, TicketState
from planfile.sync.github import GitHubBackend
from planfile.sync.state import SyncState


class Backend:
    config = {"repo": "fixture/repo"}

    def __init__(self, status="closed", reason="completed"):
        self.remote = {"42": TicketState(
            id="42", name="remote title", description="remote evidence", status=status,
            url="https://github.com/fixture/repo/issues/42",
            metadata={"state_reason": reason},
        )}
        self.events = []
        self.fail = False
        self.omit = False

    def list_tickets(self, **kwargs):
        return self.list_selected_tickets(set(self.remote), **kwargs)

    def list_selected_tickets(self, ids, **kwargs):
        self.events.append(("read", sorted(ids), kwargs))
        if self.fail:
            raise TimeoutError("controlled offline inbound failure")
        return [] if self.omit else [deepcopy(t) for id, t in self.remote.items() if id in ids]

    def get_ticket(self, id):
        return self.remote[str(id)]

    def update_ticket(self, id, **fields):
        self.events.append(("update", str(id), fields))
        if "status" in fields:
            self.remote[str(id)].status = GitHubBackend.project_remote_status(fields["status"])
        self.remote[str(id)].name = fields["name"]
        self.remote[str(id)].description = fields["body"]

    def create_ticket(self, ticket):
        self.events.append(("create", ticket))
        self.remote["900"] = TicketState(
            id="900", name=ticket["name"], description=ticket.get("description", ""),
            status=GitHubBackend.project_remote_status(ticket.get("status")),
        )
        return TicketRef(id="900", url="https://github.com/fixture/repo/issues/900")


@pytest.fixture(params=["yaml", "sharded", "legacy"])
def sample(tmp_path, request):
    selected = {"id": "PLF-001", "name": "stale title", "status": "open",
                "sprint": "backlog", "integration": ["github"],
                "sync": {"github": {"id": "42", "repository": "fixture/repo"}}}
    unrelated = {**deepcopy(selected), "id": "PLF-002", "name": "unrelated",
                 "sync": {"github": {"id": "43", "repository": "fixture/repo"}}}
    store = PlanfileStore(tmp_path)
    legacy = request.param == "legacy"
    if legacy:
        (tmp_path / "tickets.planfile.yaml").write_text(yaml.safe_dump({
            "backlog": {"tickets": {t["id"]: t for t in [selected, unrelated]}}
        }))
    else:
        store.init()
        for t in [selected, unrelated]:
            store.create_ticket(Ticket(**t))
        if request.param == "sharded":
            store.migrate_to_sharded_yaml()
    return store, Backend(), legacy


def loaded(sample):
    store, _, _ = sample
    return core._load_tickets_for_sync(store, str(store.project_dir), "github")


def records(sample):
    return dict(loaded(sample)[0])


def replace_record(sample, id, **changes):
    store, _, legacy = sample
    if legacy:
        path = store.project_dir / "tickets.planfile.yaml"
        data = yaml.safe_load(path.read_text())
        data["backlog"]["tickets"][id].update(changes)
        path.write_text(yaml.safe_dump(data))
    else:
        store.update_ticket(id, **changes)


def run(sample, direction="both", dry_run=False):
    store, backend, _ = sample
    tickets, _, source, data = core._load_tickets_for_sync(
        store, str(store.project_dir), "github", ticket_ids=["PLF-001"]
    )
    core._execute_sync_with_progress(
        backend, tickets, dry_run, store, "github", source, data, direction,
        ticket_ids=["PLF-001"],
    )


@pytest.mark.parametrize("reason,status", [("completed", "done"), ("not_planned", "canceled"), (None, "blocked")])
def test_remote_closure_is_not_reopened_and_scoped_snapshot_is_reloaded(sample, reason, status):
    store, backend, _ = sample
    backend.remote["42"].metadata["state_reason"] = reason
    untouched = deepcopy(records(sample)["PLF-002"])
    if status == "blocked":
        with pytest.raises(typer.Exit) as caught:
            run(sample)
        assert caught.value.exit_code == 2
    else:
        run(sample)
    after = records(sample)
    assert after["PLF-001"]["status"] == status
    assert after["PLF-001"]["name"] == "remote title"
    assert after["PLF-002"] == untouched
    assert backend.events[0][0] == "read"
    assert backend.remote["42"].status == "closed"
    updates = [e for e in backend.events if e[0] == "update"]
    assert len(updates) == (0 if status == "blocked" else 1)
    if updates:
        assert updates[0][2]["name"] == "remote title"
        assert "status" not in updates[0][2]


@pytest.mark.parametrize("local,remote", [("blocked", "closed"), ("done", "open"), ("canceled", "open"), ("failed", "open")])
def test_conflicting_native_lifecycle_is_preserved_on_both_sides(sample, local, remote):
    replace_record(sample, "PLF-001", status=local)
    backend = sample[1]
    backend.remote["42"].status = remote
    with pytest.raises(typer.Exit) as caught:
        run(sample)
    assert caught.value.exit_code == 2
    assert records(sample)["PLF-001"]["status"] == local
    assert backend.remote["42"].status == remote
    assert [e[0] for e in backend.events] == ["read"]


def test_matching_blocked_open_mapping_can_still_publish_content(sample):
    replace_record(sample, "PLF-001", status="blocked")
    sample[1].remote["42"].status = "open"
    run(sample)
    assert [e[0] for e in sample[1].events] == ["read", "update"]
    assert records(sample)["PLF-001"]["status"] == "blocked"


def test_unobserved_mapping_is_not_blindly_published(sample):
    sample[1].omit = True
    before = deepcopy(records(sample))
    with pytest.raises(typer.Exit) as caught:
        run(sample)
    assert caught.value.exit_code == 2
    assert records(sample) == before
    assert [e[0] for e in sample[1].events] == ["read"]


def test_inbound_failure_prevents_any_outbound_mutation(sample):
    sample[1].fail = True
    before = deepcopy(records(sample))
    with pytest.raises(RuntimeError, match="sync_inbound_fetch_failed"):
        run(sample)
    assert records(sample) == before
    assert [e[0] for e in sample[1].events] == ["read"]


def test_both_dry_run_previews_inbound_without_stale_outbound_or_writes(sample, capsys):
    store, backend, _ = sample
    before = deepcopy(records(sample))
    run(sample, dry_run=True)
    assert records(sample) == before
    assert [e[0] for e in backend.events] == ["read"]
    assert not (store.base_dir / "sync/github.receipts.jsonl").exists()
    assert "Outbound preview deferred" in capsys.readouterr().out


def test_explicit_to_can_apply_local_lifecycle_without_inbound(sample):
    run(sample, direction="to")
    assert [e[0] for e in sample[1].events] == ["update"]
    assert sample[1].remote["42"].status == "open"


def test_from_remains_read_only_towards_provider(sample):
    run(sample, direction="from")
    assert [e[0] for e in sample[1].events] == ["read"]
    assert records(sample)["PLF-001"]["status"] == "done"


def test_unmapped_local_ticket_can_be_published_after_inbound(sample):
    replace_record(sample, "PLF-001", sync={})
    run(sample)
    assert [e[0] for e in sample[1].events] == ["read", "create"]
    assert records(sample)["PLF-001"]["sync"]["github"]["id"] == "900"


def test_state_file_only_mapping_receives_same_protection(sample):
    replace_record(sample, "PLF-001", sync={})
    store, backend, _ = sample
    SyncState.from_backend(store.base_dir, "github", backend).save_sync({"PLF-001": "42"})
    backend.omit = True
    with pytest.raises(typer.Exit) as caught:
        run(sample)
    assert caught.value.exit_code == 2
    assert [e[0] for e in backend.events] == ["read"]


def test_non_github_both_retains_existing_phase_order(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(core, "sync_from_external", lambda *a, **kw: calls.append("from"))
    monkeypatch.setattr(core, "sync_to_external", lambda *a, **kw: calls.append("to"))
    core._execute_sync_with_progress(object(), [], False, PlanfileStore(tmp_path), "jira", None, None, "both")
    assert calls == ["to", "from"]


def test_both_preserves_unpublished_planning_and_publishes_it(sample):
    planning = "accepted local scope not published yet"
    replace_record(sample, "PLF-001", description=planning)
    run(sample)
    assert records(sample)["PLF-001"]["description"] == planning
    assert sample[1].remote["42"].description == planning
    assert sample[1].remote["42"].status == "closed"


def test_explicit_from_retains_intentional_remote_description_import(sample):
    replace_record(sample, "PLF-001", description="unpublished local plan")
    run(sample, direction="from")
    assert records(sample)["PLF-001"]["description"] == "remote evidence"
    assert [event[0] for event in sample[1].events] == ["read"]


@pytest.mark.parametrize("sample", ["yaml", "sharded"], indirect=True)
def test_native_preserves_snapshot_plan_newer_than_initial_selection(sample):
    store, backend, legacy = sample
    tickets, _, source, data = core._load_tickets_for_sync(
        store, str(store.project_dir), "github", ticket_ids=["PLF-001"]
    )
    store.update_ticket("PLF-001", description="newer accepted scope before inbound snapshot")
    core._execute_sync_with_progress(
        backend, tickets, False, store, "github", source, data, "both",
        ticket_ids=["PLF-001"],
    )
    assert records(sample)["PLF-001"]["description"] == "newer accepted scope before inbound snapshot"
    assert backend.remote["42"].description == "newer accepted scope before inbound snapshot"


@pytest.mark.parametrize("sample", ["yaml", "sharded"], indirect=True)
def test_native_cas_still_rejects_owner_update_during_fetch(sample, monkeypatch):
    store, backend, legacy = sample
    original = backend.list_selected_tickets

    def concurrent(*args, **kwargs):
        store.update_ticket("PLF-001", description="concurrent owner plan")
        return original(*args, **kwargs)

    monkeypatch.setattr(backend, "list_selected_tickets", concurrent)
    with pytest.raises(ValueError):
        run(sample)
    assert records(sample)["PLF-001"]["description"] == "concurrent owner plan"
    assert [event[0] for event in backend.events] == ["read"]


@pytest.mark.parametrize("sample", ["yaml", "sharded"], indirect=True)
def test_native_live_worker_is_not_closed_by_both(sample):
    _, backend, legacy = sample
    replace_record(sample, "PLF-001", status="in_progress", description="active owner plan",
                   execution={"state": "running", "assigned_to": "other-owner",
                              "lease_expires_at": "2099-01-01T00:00:00Z"})
    before = deepcopy(records(sample)["PLF-001"])
    with pytest.raises(ValueError, match="execution_reconciliation"):
        run(sample)
    assert records(sample)["PLF-001"] == before
    assert [event[0] for event in backend.events] == ["read"]


def test_closure_during_metadata_update_survives_and_fails_readback(sample, monkeypatch):
    backend = sample[1]
    backend.remote["42"].status = "open"
    original = backend.update_ticket

    def concurrent(remote_id, **fields):
        backend.remote[remote_id].status = "closed"
        return original(remote_id, **fields)

    monkeypatch.setattr(backend, "update_ticket", concurrent)
    from planfile.sync.outbound import OutboundSyncError
    with pytest.raises(OutboundSyncError):
        run(sample)
    assert backend.remote["42"].status == "closed"
    assert "status" not in next(event[2] for event in backend.events if event[0] == "update")


def test_observer_keeps_numeric_repository_identity_validation(sample):
    from planfile.sync.state import SyncStateRepositoryMismatch
    store, _, _ = sample

    class IdentityBackend(Backend):
        def resolve_repository_identity(self, repository=None):
            self.events.append(("identity", repository))
            return {"repository": "fixture/repo", "repository_id": "999"}

    backend = IdentityBackend()
    state = SyncState(store.base_dir, "github", repository="fixture/repo")
    state.state_file.parent.mkdir(parents=True, exist_ok=True)
    state.state_file.write_text(yaml.safe_dump({"version": 2, "backend": "github",
        "repository": "fixture/repo", "repository_id": "123", "ticket_map": {"PLF-001": "42"}}))
    before = state.state_file.read_bytes()
    tickets, _, source, data = loaded(sample)
    with pytest.raises(SyncStateRepositoryMismatch):
        core._execute_sync_with_progress(backend, tickets, False, store, "github",
            source, data, "both", ticket_ids=["PLF-001"])
    assert state.state_file.read_bytes() == before
    assert all(event[0] == "identity" for event in backend.events)


def test_selected_conflict_does_not_hide_safe_other_delivery(sample):
    store, backend, _ = sample
    replace_record(sample, "PLF-001", status="blocked")
    backend.remote["43"] = backend.remote["42"].model_copy(update={"id": "43",
        "url": "https://github.com/fixture/repo/issues/43"})
    tickets, _, source, data = loaded(sample)
    with pytest.raises(typer.Exit) as caught:
        core._execute_sync_with_progress(backend, tickets, False, store, "github",
            source, data, "both", ticket_ids=["PLF-001", "PLF-002"])
    assert caught.value.exit_code == 2
    assert [event[1] for event in backend.events if event[0] == "update"] == ["43"]
    assert records(sample)["PLF-001"]["status"] == "blocked"
    assert records(sample)["PLF-002"]["status"] == "done"


@pytest.mark.parametrize("sample", ["yaml", "sharded"], indirect=True)
@pytest.mark.parametrize("field", ["description", "outputs", "execution"])
def test_native_outbound_preserves_same_revision_owner_write(sample, monkeypatch, field):
    from planfile.sync.outbound import OutboundSyncError
    store, backend, _ = sample
    backend.remote["42"].status = "open"
    original = backend.update_ticket
    def concurrent(*args, **kwargs):
        result = original(*args, **kwargs)
        section = store.load_backlog()
        ticket = section["tickets"]["PLF-001"]
        if field == "description":
            ticket[field] = "late accepted owner plan"
        elif field == "outputs":
            ticket[field] = {"notes": ["late private owner note"]}
        else:
            ticket["status"] = "in_progress"
            ticket[field] = {"state": "running", "assigned_to": "late-owner",
                             "lease_expires_at": "2099-01-01T00:00:00Z"}
        store.save_backlog(section)
        return result
    monkeypatch.setattr(backend, "update_ticket", concurrent)
    with pytest.raises((OutboundSyncError, ValueError)):
        run(sample)
    ticket = records(sample)["PLF-001"]
    if field == "description":
        assert ticket[field] == "late accepted owner plan"
    elif field == "outputs":
        assert ticket[field]["notes"] == ["late private owner note"]
    else:
        assert ticket["status"] == "in_progress" and ticket[field]["assigned_to"] == "late-owner"


@pytest.mark.parametrize("sample", ["yaml", "sharded"], indirect=True)
def test_native_outbound_checks_snapshot_before_remote_write(sample, monkeypatch):
    from planfile.sync.outbound import OutboundSyncError
    store, backend, _ = sample
    backend.remote["42"].status = "open"
    def preflight(_tickets):
        section = store.load_backlog()
        section["tickets"]["PLF-001"]["description"] = "owner changed before send"
        store.save_backlog(section)
    monkeypatch.setattr(backend, "preflight", preflight, raising=False)
    with pytest.raises((OutboundSyncError, ValueError)):
        run(sample)
    assert all(event[0] not in {"update", "create"} for event in backend.events)
    assert records(sample)["PLF-001"]["description"] == "owner changed before send"
