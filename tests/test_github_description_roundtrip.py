"""Exercise actual provider projection and durable outbound retries together."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from planfile.core.store import Store
from planfile.sync.github import GitHubBackend
from planfile.sync.operations import sync_from_external
from planfile.sync.outbound import OutboundSyncError, sync_to_external

START = GitHubBackend.DESCRIPTION_START
END = GitHubBackend.DESCRIPTION_END


class Issue(SimpleNamespace):
    def __init__(self, body="human evidence  \n", number=42):
        super().__init__(body=body, number=number, title="remote title", state="open",
                         html_url=f"https://github.com/owner/repo/issues/{number}",
                         labels=[], pull_request=None, edits=[], ignore_body=False)

    def edit(self, **fields):
        self.edits.append(fields)
        for key, value in fields.items():
            if key != "body" or not self.ignore_body:
                setattr(self, key, value)

    def set_labels(self, *labels):
        self.labels = list(labels)


class Repo:
    full_name = "owner/repo"

    def __init__(self, issue):
        self.issue = issue
        self.created = []
        self.missing = False

    def get_issue(self, number):
        if self.missing:
            raise RuntimeError("404 Not Found")
        assert number == self.issue.number
        return self.issue

    def get_issues(self, **kwargs):
        return [self.issue] if self.issue else []

    def get_labels(self):
        return []

    def create_label(self, **kwargs):
        pass

    def create_issue(self, **fields):
        self.created.append(fields)
        self.issue = Issue(fields["body"])
        self.issue.title = fields["title"]
        return self.issue


def backend(tmp_path, issue=None):
    result = GitHubBackend.__new__(GitHubBackend)
    result.config = {"repo": "owner/repo", "cache_dir": str(tmp_path / "cache")}
    result.repo = Repo(issue)
    result._mutation_interval = 0
    result._last_mutation_at = 0
    return result


def publication(tmp_path):
    issue = Issue()
    provider = backend(tmp_path, issue)
    store = Store(tmp_path)
    store.init()
    ticket = {"id": "PLF-1", "name": "local title", "description": "accepted plan",
              "status": "open", "sync": {"github": {"id": "42", "repository": "owner/repo"}}}
    return provider, issue, store, ticket


def test_repeated_roundtrips_project_only_owned_text_and_preserve_outside_bytes(tmp_path):
    issue = Issue()
    provider = backend(tmp_path, issue)
    provider.update_ticket("42", body="accepted plan")
    issue.body += "\n\nhuman decision  \n"
    expected = issue.body
    for _ in range(4):
        remote = provider.get_ticket("42")
        assert remote.description == "accepted plan"
        provider.update_ticket("42", body=remote.description)
    assert issue.body == expected
    assert issue.body.count(START) == 1
    assert len(issue.edits) == 1


def test_legacy_unmarked_imports_remain_explicit(tmp_path):
    issue = Issue("legacy human body  \n")
    assert backend(tmp_path, issue).get_ticket("42").description == issue.body


def test_empty_clears_owned_description_and_none_leaves_it_unchanged(tmp_path):
    provider, issue, store, ticket = publication(tmp_path)
    sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    ticket.update(description="", body="stale legacy alias")
    sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    assert provider.get_ticket("42").description == ""
    assert "stale legacy alias" not in issue.body
    assert issue.body.startswith("human evidence  \n")
    expected = issue.body
    provider.update_ticket("42", body=None)
    assert issue.body == expected


@pytest.mark.parametrize("body", [START, END, END + START, START + START + END,
                                       START + END + END, START + END + START + END])
def test_ambiguous_markers_fail_reads_and_updates_before_mutation(tmp_path, body):
    issue = Issue(body)
    provider = backend(tmp_path, issue)
    with pytest.raises(ValueError, match="description_markers_ambiguous"):
        provider.get_ticket("42")
    with pytest.raises(ValueError, match="description_markers_ambiguous"):
        provider.update_ticket("42", body="new plan", status="closed", labels=[])
    assert issue.edits == []
    assert issue.body == body
    assert issue.state == "open"


@pytest.mark.parametrize("marker", [START, END])
def test_reserved_local_markers_fail_before_create_or_update(tmp_path, marker):
    issue = Issue()
    provider = backend(tmp_path, issue)
    with pytest.raises(ValueError, match="contains_reserved_marker"):
        provider.create_ticket({"name": "test", "description": marker})
    with pytest.raises(ValueError, match="contains_reserved_marker"):
        provider.update_ticket("42", body=marker)
    assert provider.repo.created == []
    assert issue.edits == []


@pytest.mark.parametrize("description", ["accepted plan", ""])
def test_managed_create_and_marker_recovery_preserve_one_region_and_payload(tmp_path, description):
    provider = backend(tmp_path)
    payload = {"name": "test", "description": description,
               "metadata": {"planfile_id": "store:PLF-1"}}
    original = deepcopy(payload)
    reference = provider.create_ticket(payload)
    assert payload == original
    issue = provider.repo.issue
    issue.body += "\nhuman recovery evidence"
    expected = issue.body
    recovered = provider.create_ticket(payload)
    assert recovered.id == reference.id
    assert len(provider.repo.created) == 1
    assert issue.body == expected
    assert issue.body.count(START) == 1
    assert provider.get_ticket(reference.id).description == description
    assert issue.body.index("planfile:deduplication-key=") < issue.body.index(START)
    changed = {**payload, "description": "changed accepted plan"}
    assert provider.create_ticket(changed).id == reference.id
    assert provider.get_ticket(reference.id).description == "changed accepted plan"
    assert issue.body.endswith("human recovery evidence")
    assert len(provider.repo.created) == 1


def test_ambiguous_marker_match_never_creates_or_changes_lifecycle(tmp_path):
    issue = Issue("<!-- planfile:deduplication-key=owner/repo:PLF-1 -->\n" + START)
    provider = backend(tmp_path, issue)
    with pytest.raises(ValueError, match="markers_ambiguous"):
        provider.create_ticket({"name": "test", "description": "accepted plan", "status": "closed",
                                "metadata": {"planfile_id": "PLF-1"}})
    assert issue.edits == []
    assert issue.state == "open"
    assert provider.repo.created == []


def test_receipt_reuse_verifies_owned_text_and_repairs_same_issue(tmp_path):
    provider, issue, store, ticket = publication(tmp_path)
    sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    issue.body += "\nnew human evidence"
    edits = len(issue.edits)
    reused = sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    assert reused.reused == ("PLF-1",)
    assert len(issue.edits) == edits
    issue.body = issue.body.replace("accepted plan", "remote drift")
    repaired = sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    assert repaired.updated == ("PLF-1",)
    assert provider.get_ticket("42").description == "accepted plan"
    assert issue.body.endswith("new human evidence")
    assert provider.repo.created == []


def test_ignored_provider_edit_is_failed_and_retry_keeps_identity(tmp_path):
    provider, issue, store, ticket = publication(tmp_path)
    issue.ignore_body = True
    with pytest.raises(OutboundSyncError) as error:
        sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    assert error.value.result.failed == ("PLF-1",)
    issue.ignore_body = False
    repaired = sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    assert repaired.succeeded == ("PLF-1",)
    assert ticket["sync"]["github"]["id"] == "42"
    assert provider.repo.created == []


def test_missing_mapped_issue_without_receipt_never_creates_or_remaps(tmp_path):
    provider, issue, store, ticket = publication(tmp_path)
    provider.repo.missing = True
    with pytest.raises(OutboundSyncError):
        sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    assert ticket["sync"]["github"]["id"] == "42"
    assert provider.repo.created == []


def test_wrong_repository_binding_fails_before_mutation(tmp_path):
    provider, issue, store, ticket = publication(tmp_path)
    ticket["sync"]["github"]["repository"] = "other/repo"
    with pytest.raises(OutboundSyncError):
        sync_to_external(provider, [("PLF-1", ticket)], False, store, "github")
    assert issue.edits == []
    assert provider.repo.created == []


def test_transparent_proxy_retains_description_readback_contract(tmp_path):
    provider, issue, store, ticket = publication(tmp_path)

    class Proxy:
        def __getattr__(self, name):
            return getattr(provider, name)

    issue.ignore_body = True
    with pytest.raises(OutboundSyncError):
        sync_to_external(Proxy(), [("PLF-1", ticket)], False, store, "github")


@pytest.mark.parametrize("sharded", [False, True])
def test_real_sdk_roundtrip_keeps_description_and_concurrency_guards(tmp_path, sharded):
    from planfile.core.store import Ticket, TicketUpdatedAtConflictError

    store = Store(tmp_path)
    store.init()
    store.create_ticket(Ticket(id="PLF-001", name="local", description="accepted plan",
                               status="open", sprint="backlog", integration=["github"],
                               sync={"github": {"id": "42", "repository": "owner/repo"}}))
    if sharded:
        store.migrate_to_sharded_yaml()
    desired = store.get_ticket("PLF-001").description
    issue = Issue(GitHubBackend._merge_description("human evidence", desired))
    provider = backend(tmp_path, issue)
    sync_from_external(provider, store, False, "github", ticket_ids=["PLF-001"])
    before = store.get_ticket("PLF-001")
    assert before.description == desired
    issue.body += "\nnew human discussion"
    sync_from_external(provider, store, False, "github", ticket_ids=["PLF-001"])
    assert store.get_ticket("PLF-001").model_dump(mode="json") == before.model_dump(mode="json")
    issue.body = provider._merge_description(issue.body, "remote accepted edit")
    sync_from_external(provider, store, False, "github", ticket_ids=["PLF-001"])
    with pytest.raises(TicketUpdatedAtConflictError):
        store.update_ticket("PLF-001", expected_updated_at=before.updated_at, description="stale writer")
    assert store.get_ticket("PLF-001").description == "remote accepted edit"
    store.update_ticket("PLF-001", status="in_progress", execution={
        "state": "running", "assigned_to": "other", "lease_expires_at": "2099-01-01T00:00:00Z"})
    before = store.get_ticket("PLF-001").model_dump(mode="json")
    issue.state = "closed"
    issue.state_reason = "completed"
    with pytest.raises(ValueError, match="execution_reconciliation"):
        sync_from_external(provider, store, False, "github", ticket_ids=["PLF-001"])
    assert store.get_ticket("PLF-001").model_dump(mode="json") == before
