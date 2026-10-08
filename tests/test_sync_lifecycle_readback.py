"""A publication receipt proves identity, not the current GitHub lifecycle."""

import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from planfile.core.store import Store
from planfile.sync.github import GitHubBackend
from planfile.sync.outbound import OutboundSyncError, sync_to_external


class Issue(SimpleNamespace):
    def edit(self, **fields):
        if not self.ignore_state:
            self.__dict__.update(fields)
        self.edits.append(fields)

    def set_labels(self, *labels):
        self.labels = list(labels)


class Repo:
    full_name = "owner/repo"

    def __init__(self):
        self.issue = None
        self.creates = 0
        self.reads = 0
        self.unavailable = False

    def create_issue(self, **fields):
        self.creates += 1
        self.issue = Issue(number=42, html_url="https://github.com/owner/repo/issues/42",
                           state="open", title=fields["title"], body=fields["body"],
                           labels=[], ignore_state=False, edits=[])
        return self.issue

    def get_issue(self, number):
        self.reads += 1
        if self.unavailable:
            raise RuntimeError("offline")
        assert number == 42
        return self.issue


def backend():
    b = GitHubBackend.__new__(GitHubBackend)
    b.config = {"repo": "owner/repo"}
    b.repo = Repo()
    b.preflight = lambda tickets: None
    b._prepare_labels = lambda *args: []
    b._creation_lock = lambda key: nullcontext()
    b._find_issue_by_markers = lambda markers: b.repo.issue
    b._cache_marker_result = lambda *args: None
    b._throttle_mutation = lambda: None
    return b


def ticket(status="done"):
    return {"id": "PLF-1", "name": "lifecycle task", "description": "verified work",
            "status": status, "integration": ["github"]}


def run(b, t, store):
    return sync_to_external(b, [(t["id"], t)], False, store, "github")


@pytest.mark.parametrize("status", ["done", "failed", "canceled", "completed"])
def test_terminal_create_and_deduplicated_create_close_same_issue(status):
    b = backend()
    t = ticket(status)
    first = b.create_ticket(t)
    assert first.status == "closed"
    assert b.repo.issue.state == "closed"
    b.repo.issue.state = "open"
    second = b.create_ticket(t)
    assert second.id == first.id
    assert second.status == "closed"
    assert b.repo.creates == 1


@pytest.mark.parametrize("status", ["open", "in_progress", "review", "triage", "blocked"])
def test_active_create_and_dedup_project_to_open(status):
    b = backend()
    first = b.create_ticket(ticket(status))
    assert first.status == "open"
    b.repo.issue.state = "closed"
    second = b.create_ticket(ticket(status))
    assert second.id == first.id and second.status == "open"
    assert b.repo.creates == 1


def test_successful_receipt_retry_reconciles_drift_without_duplicate(tmp_path):
    store = Store(tmp_path)
    store.init()
    b, t = backend(), ticket()
    assert run(b, t, store).succeeded == ("PLF-1",)
    b.repo.issue.state = "open"
    before_reads = b.repo.reads
    result = run(b, t, store)
    assert result.succeeded == ("PLF-1",)
    assert result.updated == ("PLF-1",)
    assert b.repo.issue.state == "closed"
    assert b.repo.reads > before_reads
    assert b.repo.creates == 1
    reads, edits = b.repo.reads, len(b.repo.issue.edits)
    assert run(b, t, store).reused == ("PLF-1",)
    assert b.repo.reads > reads
    assert len(b.repo.issue.edits) == edits


def test_blocked_update_reopens_issue_and_retry_preserves_local_blocker(tmp_path):
    store = Store(tmp_path)
    store.init()
    b, t = backend(), ticket("done")
    assert run(b, t, store).succeeded == ("PLF-1",)
    assert b.repo.issue.state == "closed"

    t["status"] = "blocked"
    t["description"] = "Waiting for the owner to hand off the active lease."
    result = run(b, t, store)
    assert result.updated == ("PLF-1",)
    assert result.failed == ()
    assert b.repo.issue.state == "open"
    assert t["status"] == "blocked"
    assert t["description"] in b.repo.issue.body
    assert b.repo.creates == 1

    edits = len(b.repo.issue.edits)
    assert run(b, t, store).reused == ("PLF-1",)
    assert b.repo.issue.state == "open"
    assert len(b.repo.issue.edits) == edits


@pytest.mark.parametrize("status", [" BLOCKED ", "Blocked"])
def test_blocked_status_normalization_keeps_issue_open(status):
    b = backend()
    assert b.create_ticket(ticket(status)).status == "open"


def test_receipt_retry_fails_on_unavailable_readback_and_records_failure(tmp_path):
    store = Store(tmp_path)
    store.init()
    b, t = backend(), ticket()
    run(b, t, store)
    b.repo.unavailable = True
    with pytest.raises(OutboundSyncError) as caught:
        run(b, t, store)
    assert caught.value.result.failed == ("PLF-1",)
    assert caught.value.result.succeeded == ()
    rows = [json.loads(line) for line in (store.base_dir / "sync/github.receipts.jsonl").read_text().splitlines()]
    assert [row["outcome"] for row in rows] == ["succeeded", "failed"]
    b.repo.unavailable = False
    assert run(b, t, store).succeeded == ("PLF-1",)
    assert b.repo.creates == 1


def test_update_mismatch_never_counts_as_success(tmp_path):
    store = Store(tmp_path)
    store.init()
    b, t = backend(), ticket("open")
    run(b, t, store)
    t["status"] = "done"
    b.repo.issue.ignore_state = True
    with pytest.raises(OutboundSyncError) as caught:
        run(b, t, store)
    assert caught.value.result.succeeded == ()
    assert caught.value.result.failed == ("PLF-1",)
    assert b.repo.issue.state == "open"


def test_github_readback_invalidates_provider_cache():
    b = backend()
    b.repo.create_issue(title="t", body="")
    calls = []
    b._provider_read_cache = SimpleNamespace(clear=lambda: calls.append("provider"))
    b._read_cache = SimpleNamespace(clear=lambda: calls.append("metadata"))
    b.get_ticket("42")
    assert calls == ["metadata", "provider"]


def test_retry_rejects_pull_request_binding_without_mutation(tmp_path):
    store = Store(tmp_path)
    store.init()
    b, t = backend(), ticket()
    run(b, t, store)
    edits = len(b.repo.issue.edits)
    b.repo.issue.pull_request = {"url": "https://github.com/owner/repo/pull/42"}
    with pytest.raises(OutboundSyncError):
        run(b, t, store)
    assert len(b.repo.issue.edits) == edits
    assert b.repo.creates == 1
