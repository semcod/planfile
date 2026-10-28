"""Public SDK contracts: selection bounds provider I/O without waiving writes."""

from types import SimpleNamespace

import pytest

from planfile.core.store import PlanfileStore, Ticket, TicketUpdatedAtConflictError
from planfile.sync.github import GitHubBackend
from planfile.sync.operations import sync_from_external


@pytest.fixture(params=[False, True], ids=["yaml", "sharded"])
def sample(tmp_path, request):
    store = PlanfileStore(tmp_path)
    store.init()
    store.create_ticket(
        Ticket(
            id="PLF-001",
            name="selected",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={"github": {"id": "553", "repository": "fixture/repo"}},
        )
    )
    store.create_ticket(
        Ticket(
            id="PLF-002",
            name="unrelated",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={"github": {"id": "554", "repository": "fixture/repo"}},
        )
    )
    if request.param:
        store.migrate_to_sharded_yaml()
    calls = []

    def issue(number):
        return SimpleNamespace(
            number=number,
            title="remote " + str(number),
            body="closed evidence",
            state="closed",
            state_reason="completed",
            pull_request=None,
            assignee=None,
            labels=[SimpleNamespace(name="managed")],
            updated_at=None,
            html_url="https://github.com/fixture/repo/issues/" + str(number),
        )

    class Repo:
        full_name = "fixture/repo"
        callback = None
        override = None

        def get_issues(self, **kwargs):
            calls.append(("list", kwargs))
            raise AssertionError("Unrelated pages must not be read")

        def get_issue(self, number):
            calls.append(("get", number))
            if self.callback:
                self.callback(number)
            return self.override or issue(number)

    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "fixture/repo"}
    backend.repo = Repo()
    return store, backend, calls, issue


def pull(sample, selectors=None, **kwargs):
    store, backend, *_ = sample
    return sync_from_external(
        backend, store, False, "github", ticket_ids=selectors or ["PLF-001"], **kwargs
    )


def unchanged(store):
    return [store.get_ticket(id).model_dump(mode="json") for id in ["PLF-001", "PLF-002"]]


@pytest.mark.parametrize("selector", ["PLF-001", "553", "#553", "fixture/repo#553"])
def test_exact_selected_sync_succeeds_when_unrelated_listing_is_unavailable(sample, selector):
    store, backend, calls, _ = sample
    before = store.get_ticket("PLF-001")
    unrelated = unchanged(store)[1]
    pull(sample, [selector])
    after = store.get_ticket("PLF-001")
    assert (
        calls == [("get", 553)] and after.status == "done" and after.updated_at != before.updated_at
    )
    assert (
        after.execution.state == "done"
        and after.execution.assigned_to is None
        and after.execution.lease_expires_at is None
    )
    assert unchanged(store)[1] == unrelated
    with pytest.raises(TicketUpdatedAtConflictError):
        store.update_ticket(after.id, expected_updated_at=before.updated_at, description="stale")


def test_duplicate_selectors_read_once(sample):
    pull(sample, ["PLF-001", "553", "#553", "fixture/repo#553"])
    assert sample[2] == [("get", 553)]


def test_multiple_reads_finish_before_any_ticket_write(sample):
    store, backend, calls, _ = sample
    before = unchanged(store)

    def callback(number):
        assert unchanged(store) == before
        if number == 554:
            raise TimeoutError("selected provider failure")

    backend.repo.callback = callback
    with pytest.raises(RuntimeError, match="sync_inbound_fetch_failed") as caught:
        pull(sample, ["PLF-001", "PLF-002"])
    assert isinstance(caught.value.__cause__, TimeoutError)
    assert calls == [("get", 553), ("get", 554)] and unchanged(store) == before


def test_selected_concurrent_mutation_rejects_stale_write(sample):
    store, backend, *_ = sample
    backend.repo.callback = lambda _: store.update_ticket(
        "PLF-001", description="foreign concurrent owner"
    )
    with pytest.raises(ValueError):
        pull(sample)
    assert (
        store.get_ticket("PLF-001").status == "open"
        and store.get_ticket("PLF-001").description == "foreign concurrent owner"
    )


def test_live_execution_cannot_be_released_by_direct_read(sample):
    store, *_ = sample
    store.update_ticket(
        "PLF-001",
        status="in_progress",
        execution={
            "state": "running",
            "assigned_to": "foreign",
            "lease_expires_at": "2099-01-01T00:00:00Z",
        },
    )
    before = unchanged(store)
    with pytest.raises(ValueError, match="execution_reconciliation"):
        pull(sample)
    assert unchanged(store) == before


def test_unrelated_concurrent_update_is_preserved(sample):
    store, backend, *_ = sample
    backend.repo.callback = lambda _: store.update_ticket(
        "PLF-002", description="concurrent unrelated"
    )
    pull(sample)
    assert (
        store.get_ticket("PLF-001").status == "done"
        and store.get_ticket("PLF-002").description == "concurrent unrelated"
    )


def test_direct_dry_run_never_changes_ticket(sample):
    store, backend, calls, _ = sample
    before = unchanged(store)
    sync_from_external(backend, store, True, "github", ticket_ids=["PLF-001"])
    assert unchanged(store) == before and calls == [("get", 553)]


@pytest.mark.parametrize("labels", [["managed"], ["managed", "missing"]])
def test_managed_label_filter_is_preserved(sample, labels):
    store, *_ = sample
    before = unchanged(store)
    pull(sample, remote_labels=labels)
    if len(labels) == 1:
        assert store.get_ticket("PLF-001").status == "done"
    else:
        assert unchanged(store) == before


@pytest.mark.parametrize(
    "selector", ["PLF-missing", "other/repo#553", "0553", "#0553", "0", "-1", "٥٥٣"]
)
def test_unresolved_selector_does_not_fall_back_to_listing(sample, selector):
    store, _, calls, _ = sample
    before = unchanged(store)
    pull(sample, [selector])
    assert not calls and unchanged(store) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("number", 554),
        ("html_url", "https://github.com/other/repo/issues/553"),
        ("pull_request", {"url": "PR"}),
    ],
)
def test_wrong_provider_packet_rejected_without_local_change(sample, field, value):
    store, backend, _, issue = sample
    before = unchanged(store)
    packet = issue(553)
    setattr(packet, field, value)
    backend.repo.override = packet
    with pytest.raises(RuntimeError, match="sync_inbound_fetch_failed"):
        pull(sample)
    assert unchanged(store) == before


def test_selected_cross_repository_mapping_rejected_before_issue_read(sample):
    store, _, calls, _ = sample
    t = store.get_ticket("PLF-001")
    store.update_ticket(t.id, sync={"github": {"id": "553", "repository": "other/repo"}})
    before = unchanged(store)
    with pytest.raises(ValueError, match="maps to"):
        pull(sample)
    assert not calls and unchanged(store) == before


def test_provider_repository_case_is_normalized(sample):
    store, backend, _, issue = sample
    backend.repo.full_name = "Fixture/Repo"
    packet = issue(553)
    packet.html_url = "https://github.com/Fixture/Repo/issues/553"
    backend.repo.override = packet
    pull(sample)
    assert store.get_ticket("PLF-001").status == "done"


def test_unscoped_sync_retains_existing_listing_contract(sample):
    store, backend, calls, issue = sample

    def list_issues(**kwargs):
        calls.append(("list", kwargs))
        return [issue(553), issue(554)]

    backend.repo.get_issues = list_issues
    sync_from_external(backend, store, False, "github")
    assert calls == [("list", {"state": "all"})] and all(
        store.get_ticket(id).status == "done" for id in ["PLF-001", "PLF-002"]
    )


def test_non_github_provider_keeps_existing_list_contract(sample):
    store, _, calls, _ = sample

    class Backend:
        config = {}

        def list_tickets(self, **kwargs):
            calls.append(("legacy", kwargs))
            return []

        def list_selected_tickets(self, *args, **kwargs):
            raise AssertionError("GitHub capability is provider-specific")

    sync_from_external(Backend(), store, False, "fixture", ticket_ids=["PLF-001"])
    assert calls == [("legacy", {})]


def test_exact_issue_read_follows_fresh_numeric_repository_proof(sample):
    store, backend, calls, _ = sample

    class Requester:
        def requestJsonAndCheck(self, verb, path):
            assert verb == "GET"
            calls.append(("identity", path))
            return {}, {"id": 42, "full_name": "fixture/repo"}

    backend._identity_requester = Requester()
    pull(sample)
    assert calls == [
        ("identity", "/repos/fixture/repo"),
        ("identity", "/repositories/42"),
        ("get", 553),
    ]
    assert store.get_ticket("PLF-001").status == "done"


def test_numeric_identity_conflict_prevents_any_selected_issue_read(sample):
    import yaml

    from planfile.sync.state import SyncState, SyncStateRepositoryMismatch

    store, backend, calls, _ = sample
    before = unchanged(store)
    state = SyncState(store.base_dir, "github", repository="fixture/repo")
    state.save_sync({"PLF-001": "553"})
    raw = yaml.safe_load(state.state_file.read_text())
    raw["repository_id"] = "999"
    state.state_file.write_text(yaml.safe_dump(raw))
    original = state.state_file.read_bytes()

    class Requester:
        def requestJsonAndCheck(self, verb, path):
            return {}, {"id": 42, "full_name": "fixture/repo"}

    backend._identity_requester = Requester()
    with pytest.raises(SyncStateRepositoryMismatch):
        pull(sample)
    assert not calls and unchanged(store) == before and state.state_file.read_bytes() == original


def test_scoped_custom_sprint_updates_selected_ticket_in_place(sample):
    store, _, calls, _ = sample
    assert store.move_ticket("PLF-001", "custom-review")
    pull(sample, sprint_ids=["custom-review"])
    assert (
        calls == [("get", 553)]
        and store.get_ticket("PLF-001").sprint == "custom-review"
        and store.get_ticket("PLF-001").status == "done"
    )


def test_unknown_sprint_does_not_read_selected_issue(sample):
    store, _, calls, _ = sample
    before = unchanged(store)
    pull(sample, sprint_ids=["missing-sprint"])
    assert not calls and unchanged(store) == before
