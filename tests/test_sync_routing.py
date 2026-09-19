from __future__ import annotations

import pytest

from planfile.cli.groups.sync.core import _load_tickets_for_sync
from planfile.sync.base import TicketState
from planfile.sync.operations import (
    _extract_ticket_data,
    _import_new_ticket,
    _ticket_external_id,
    _update_local_ticket,
)


class FakeSyncState:
    def __init__(self):
        self.mapping = {}

    def get_remote_id(self, local_id):
        return self.mapping.get(local_id)

    def save_sync(self, mapping):
        self.mapping.update(mapping)


def test_onedev_import_routes_ticket_to_github_without_losing_evidence():
    backlog = {"tickets": {}}
    state = FakeSyncState()
    external = TicketState(
        id="11",
        key="subactor/doctor-agent#2",
        name="Doctor finding",
        description="full evidence",
        url="http://onedev/subactor/doctor-agent/~issues/2",
        status="open",
        labels=["onedev:subactor/doctor-agent"],
        metadata={"deduplication_key": "doctor:abc"},
    )

    imported = _import_new_ticket(
        backlog,
        _extract_ticket_data(external),
        "onedev",
        state,
        0,
        publish_to=["github"],
    )

    ticket = backlog["tickets"]["ONEDEV-11"]
    assert imported == 1
    assert ticket["id"] == "ONEDEV-11"
    assert ticket["sprint"] == "backlog"
    assert ticket["name"] == "Doctor finding"
    assert ticket["description"] == "full evidence"
    assert ticket["integration"] == ["onedev", "github"]
    assert ticket["metadata"]["deduplication_key"] == "doctor:abc"
    assert ticket["sync"]["onedev"]["id"] == "11"


def test_backend_scoped_id_never_treats_onedev_id_as_github_issue_number():
    state = FakeSyncState()
    ticket = {
        "external_id": "11",
        "backend": "onedev",
        "sync": {"onedev": {"id": "11"}},
    }

    assert _ticket_external_id(ticket, "ONEDEV-11", "github", state) is None
    ticket["sync"]["github"] = {"id": "42"}
    assert _ticket_external_id(ticket, "ONEDEV-11", "github", state) == "42"


def test_onedev_refresh_updates_content_and_preserves_other_backend_reference():
    backlog = {
        "tickets": {
            "ONEDEV-11": {
                "name": "stale title",
                "description": "stale evidence",
                "sync": {"github": {"id": "42"}},
            }
        }
    }
    external = TicketState(
        id="11",
        key="subactor/doctor-agent#2",
        name="Current title",
        description="current evidence",
        url="http://onedev/subactor/doctor-agent/~issues/2",
        status="in_progress",
        labels=["onedev:subactor/doctor-agent"],
        metadata={"deduplication_key": "doctor:abc"},
    )

    updated = _update_local_ticket(
        {"tickets": {}},
        backlog,
        "ONEDEV-11",
        _extract_ticket_data(external),
        0,
        "onedev",
        ["github"],
    )

    ticket = backlog["tickets"]["ONEDEV-11"]
    assert updated == 1
    assert ticket["id"] == "ONEDEV-11"
    assert ticket["sprint"] == "backlog"
    assert ticket["name"] == "Current title"
    assert ticket["description"] == "current evidence"
    assert ticket["sync"]["onedev"]["id"] == "11"
    assert ticket["sync"]["github"]["id"] == "42"


class FakeSyncStore:
    def is_initialized(self):
        return True

    def _all_sprint_ids(self):
        return ["current", "history-2026-09-14", "backlog"]

    def load_sprint(self, sprint_id):
        tickets = {
            "current": {
                "PLF-001": {"name": "active", "integration": ["github"]},
            },
            "history-2026-09-14": {
                "PLF-002": {
                    "name": "resolved",
                    "status": "done",
                    "integration": ["github"],
                    "sync": {"github": {"id": "42"}},
                },
            },
            "backlog": {
                "PLF-003": {"name": "local only", "integration": ["markdown"]},
            },
        }
        return {"tickets": tickets[sprint_id]}


def test_sync_loads_mapped_history_tickets_for_external_completion():
    tickets, source, _, _ = _load_tickets_for_sync(FakeSyncStore(), ".", "github")

    assert source == ".planfile/ structure"
    assert [ticket_id for ticket_id, _ in tickets] == ["PLF-001", "PLF-002"]
    assert tickets[1][1]["status"] == "done"


def test_github_label_update_is_idempotent_and_does_not_mutate_ticket_labels(tmp_path):
    from types import SimpleNamespace

    from planfile.sync.github import GitHubBackend

    class FakeRepo:
        def get_labels(self):
            return [
                SimpleNamespace(name="planfile"),
                SimpleNamespace(name="managed"),
                SimpleNamespace(name="regression"),
                SimpleNamespace(name="priority-high"),
            ]

        def create_label(self, **kwargs):
            raise AssertionError(f"unexpected label creation: {kwargs}")

    class FakeIssue:
        def __init__(self):
            self.labels = [SimpleNamespace(name="priority: high"), SimpleNamespace(name="legacy")]
            self.set_calls = []

        def set_labels(self, *labels):
            self.set_calls.append(labels)
            self.labels = [SimpleNamespace(name=label) for label in labels]

    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "owner/repo", "cache_dir": str(tmp_path)}
    backend.repo = FakeRepo()
    issue = FakeIssue()
    ticket_labels = ["regression", "priority: high", "regression"]

    backend._update_labels(issue, ticket_labels, "high")
    backend._update_labels(issue, ticket_labels, "high")

    expected = ("regression", "priority-high", "planfile", "managed")
    assert ticket_labels == ["regression", "priority: high", "regression"]
    assert issue.set_calls == [expected, expected]


def test_github_label_cache_is_shared_by_backend_instances(tmp_path):
    from types import SimpleNamespace

    from planfile.sync.github import GitHubBackend

    class CountingRepo:
        full_name = "owner/repo"

        def __init__(self):
            self.label_reads = 0

        def get_labels(self):
            self.label_reads += 1
            return [SimpleNamespace(name="planfile"), SimpleNamespace(name="managed")]

        def create_label(self, **_kwargs):
            raise AssertionError("cache test should not create labels")

    first_repo = CountingRepo()
    first = GitHubBackend.__new__(GitHubBackend)
    first.config = {"repo": "owner/repo", "cache_dir": str(tmp_path)}
    first.repo = first_repo
    first._ensure_labels_exist(["planfile", "managed"])

    second_repo = CountingRepo()
    second = GitHubBackend.__new__(GitHubBackend)
    second.config = {"repo": "owner/repo", "cache_dir": str(tmp_path)}
    second.repo = second_repo
    second._ensure_labels_exist(["planfile", "managed"])

    assert first_repo.label_reads == 1
    assert second_repo.label_reads == 0


def test_github_marker_cache_avoids_repeating_full_issue_scan(tmp_path):
    from types import SimpleNamespace

    from planfile.sync.github import GitHubBackend

    class CountingRepo:
        full_name = "owner/repo"

        def __init__(self):
            self.issue_reads = 0

        def get_issues(self, **_kwargs):
            self.issue_reads += 1
            return [
                SimpleNamespace(
                    number=42,
                    html_url="https://github.com/owner/repo/issues/42",
                    state="open",
                    body="<!-- planfile:deduplication-key=owner/repo:PLF-1 -->",
                )
            ]

    markers = ["<!-- planfile:deduplication-key=owner/repo:PLF-1 -->"]
    first_repo = CountingRepo()
    first = GitHubBackend.__new__(GitHubBackend)
    first.config = {"repo": "owner/repo", "cache_dir": str(tmp_path)}
    first.repo = first_repo
    assert first._find_issue_by_markers(markers).number == 42

    second_repo = CountingRepo()
    second = GitHubBackend.__new__(GitHubBackend)
    second.config = {"repo": "owner/repo", "cache_dir": str(tmp_path)}
    second.repo = second_repo
    cached = second._find_issue_by_markers(markers)

    assert cached.number == 42
    assert first_repo.issue_reads == 1
    assert second_repo.issue_reads == 0


def test_github_marker_cache_short_lived_negative_result_avoids_repeat_scan(tmp_path):
    from planfile.sync.github import GitHubBackend

    class CountingRepo:
        full_name = "owner/repo"

        def __init__(self):
            self.issue_reads = 0

        def get_issues(self, **_kwargs):
            self.issue_reads += 1
            return []

    markers = ["<!-- planfile:deduplication-key=owner/repo:missing -->"]
    repo = CountingRepo()
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "owner/repo", "cache_dir": str(tmp_path)}
    backend.repo = repo

    assert backend._find_issue_by_markers(markers) is None
    assert backend._find_issue_by_markers(markers) is None
    assert repo.issue_reads == 1


def test_github_preflight_filters_internal_dedupe_labels_and_rejects_long_labels():
    from planfile.sync.github import GitHubBackend

    backend = GitHubBackend.__new__(GitHubBackend)
    backend.preflight(
        [("PLF-1", {"labels": ["dedupe:" + "x" * 120, "backend"]})]
    )

    with pytest.raises(ValueError, match="Invalid GitHub label"):
        backend.preflight(
            [("PLF-2", {"labels": ["x" * (GitHubBackend.MAX_LABEL_LENGTH + 1)]})]
        )


@pytest.mark.parametrize(
    "status",
    ["closed", "done", "completed", "blocked", "failed", "canceled", "cancelled"],
)
def test_github_projects_all_terminal_planfile_statuses_to_closed(status):
    from planfile.sync.github import GitHubBackend

    class FakeIssue:
        def __init__(self):
            self.edits = []

        def edit(self, **kwargs):
            self.edits.append(kwargs)

    issue = FakeIssue()
    GitHubBackend.__new__(GitHubBackend)._update_issue_state(issue, status)

    assert issue.edits == [{"state": "closed"}]


@pytest.mark.parametrize("status", ["open", "triage", "in_progress", "in-progress"])
def test_github_keeps_active_planfile_statuses_open(status):
    from planfile.sync.github import GitHubBackend

    class FakeIssue:
        def __init__(self):
            self.edits = []

        def edit(self, **kwargs):
            self.edits.append(kwargs)

    issue = FakeIssue()
    GitHubBackend.__new__(GitHubBackend)._update_issue_state(issue, status)

    assert issue.edits == [{"state": "open"}]


def test_github_ignores_unknown_status_without_external_mutation():
    from planfile.sync.github import GitHubBackend

    class FakeIssue:
        def edit(self, **_kwargs):
            raise AssertionError("unknown status must not mutate GitHub")

    GitHubBackend.__new__(GitHubBackend)._update_issue_state(FakeIssue(), "needs-review")


@pytest.mark.parametrize("operation", ["import", "update"])
@pytest.mark.parametrize("reason, expected", [
    ("completed", "done"), ("not_planned", "canceled"),
    (None, "blocked"), ("unknown", "blocked"),
])
def test_github_closed_roundtrip_remains_readable(tmp_path, operation, reason, expected):
    from types import SimpleNamespace

    from planfile import Planfile
    from planfile.sync.github import GitHubBackend

    backend = GitHubBackend.__new__(GitHubBackend)
    backend.repo = SimpleNamespace(full_name="owner/repo")
    issue = SimpleNamespace(number=17, title="Closed issue", body="Evidence",
                            html_url="https://github.com/owner/repo/issues/17",
                            state="closed", state_reason=reason, assignee=None,
                            labels=[], updated_at=None)
    data = _extract_ticket_data(backend._issue_to_ticket_status(issue))
    backlog = {"tickets": {}}
    if operation == "import":
        _import_new_ticket(backlog, data, "github", FakeSyncState(), 0)
        ticket_id = "GITHUB-17"
    else:
        ticket_id = "PLF-17"
        backlog["tickets"][ticket_id] = {"id": ticket_id, "name": "Old title", "status": "open"}
        _update_local_ticket({}, backlog, ticket_id, data, 0, "github", None)
    pf = Planfile(str(tmp_path))
    pf.store.save_backlog(backlog)
    reloaded = Planfile(str(tmp_path)).get_ticket(ticket_id)
    assert reloaded is not None
    assert reloaded.status.value == expected
    assert reloaded.sync["github"]["id"] == "17"
    assert backlog["tickets"][ticket_id]["metadata"]["state_reason"] == reason


@pytest.mark.parametrize("remote_status", ["open", "closed"])
@pytest.mark.parametrize("local_status", ["done", "canceled", "failed", "blocked"])
def test_github_refresh_preserves_native_terminal_or_blocked_state(remote_status, local_status):
    backlog = {"tickets": {"PLF-17": {"id": "PLF-17", "status": local_status}}}
    data = TicketState(id="17", name="Issue", status=remote_status,
                       metadata={"state_reason": "completed"}).model_dump()
    _update_local_ticket({}, backlog, "PLF-17", data, 0, "github", None)
    assert backlog["tickets"]["PLF-17"]["status"] == local_status


@pytest.mark.parametrize("local_status", ["in_progress", "review"])
def test_github_open_refresh_preserves_richer_execution_state(local_status):
    backlog = {"tickets": {"PLF-17": {"status": local_status}}}
    data = TicketState(id="17", name="Issue", status="open").model_dump()
    _update_local_ticket({}, backlog, "PLF-17", data, 0, "github", None)
    assert backlog["tickets"]["PLF-17"]["status"] == local_status


@pytest.mark.parametrize("operation", ["import", "update"])
def test_github_unknown_state_is_rejected_without_partial_write(operation):
    import copy
    backlog = {"tickets": {"PLF-17": {"name": "Original", "status": "open"}}}
    before = copy.deepcopy(backlog)
    data = TicketState(id="17", name="Changed", status="unexpected").model_dump()
    state = FakeSyncState()
    with pytest.raises(ValueError, match="Unsupported GitHub issue state"):
        if operation == "import":
            _import_new_ticket(backlog, data, "github", state, 0)
        else:
            _update_local_ticket({}, backlog, "PLF-17", data, 0, "github", None)
    assert backlog == before
    assert state.mapping == {}
