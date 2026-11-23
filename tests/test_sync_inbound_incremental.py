"""Tests for PyGithub N+1 avoidance, incremental since cursor, and empty-delta state advancement."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import yaml
from github.Issue import Issue

from planfile.core.store import PlanfileStore, Ticket
from planfile.sync.github import GitHubBackend
from planfile.sync.operations import sync_from_external


class _RawIssue:
    """Fake PyGithub Issue whose lazy properties and .raw_data fail on access."""

    def __init__(self, raw_data: dict):
        self._rawData = dict(raw_data)
        self.number = raw_data["number"]
        self.title = raw_data["title"]
        self.body = raw_data.get("body", "")
        self.state = raw_data["state"]
        self.html_url = raw_data["html_url"]
        self.updated_at = raw_data.get("updated_at")
        assignee = raw_data.get("assignee")
        self.assignee = SimpleNamespace(login=assignee) if isinstance(assignee, str) else assignee
        self.labels = [SimpleNamespace(name=lbl) for lbl in (raw_data.get("labels") or [])]

    @property
    def raw_data(self):  # pragma: no cover - CompletableGithubObject.raw_data triggers HTTP completion
        raise AssertionError("CompletableGithubObject.raw_data must not be accessed during list")

    @property
    def pull_request(self):  # pragma: no cover - must never be evaluated when _rawData is present
        raise AssertionError("Lazy Issue.pull_request HTTP completion must not run during list")

    @property
    def state_reason(self):  # pragma: no cover - must never be evaluated when _rawData is present
        raise AssertionError("Lazy Issue.state_reason HTTP completion must not run during list")


def test_github_list_tickets_avoids_lazy_issue_properties_and_forwards_since(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBACTOR_PROCACHE_PATH", str(tmp_path / "provider.sqlite3"))
    seen_github_kwargs: list[dict] = []
    seen_get_issues_kwargs: list[dict] = []

    raw_issue = _RawIssue(
        {
            "number": 10,
            "title": "Real issue",
            "body": "Body text",
            "state": "closed",
            "state_reason": "completed",
            "html_url": "https://github.com/org/repo/issues/10",
            "labels": ["bug"],
        }
    )
    raw_pr = _RawIssue(
        {
            "number": 11,
            "title": "PR item",
            "body": "PR body",
            "state": "open",
            "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/11"},
            "html_url": "https://github.com/org/repo/pull/11",
        }
    )

    class FakeRepo:
        full_name = "org/repo"

        def get_issues(self, **kwargs):
            seen_get_issues_kwargs.append(dict(kwargs))
            return [raw_issue, raw_pr]

    class FakeRequester:
        auth = None
        base_url = "https://api.github.com"

    class FakeGithub:
        def __init__(self, token, **kwargs):
            seen_github_kwargs.append(dict(kwargs))
            self.requester = FakeRequester()
            self._Github__requester = self.requester

        def get_repo(self, repo):
            return FakeRepo()

    monkeypatch.setattr("planfile.sync.github.Github", FakeGithub)
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-placeholder")
    backend = GitHubBackend("org/repo")
    since_dt = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
    tickets = backend.list_tickets(since=since_dt)

    assert seen_github_kwargs == [{"retry": 0, "per_page": 100}]
    assert seen_get_issues_kwargs == [{"state": "all", "since": since_dt}]
    assert len(tickets) == 1
    assert tickets[0].id == "10"
    assert tickets[0].metadata["state_reason"] == "completed"


def test_github_list_tickets_real_uncompleted_pygithub_issue_makes_zero_extra_http_calls(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SUBACTOR_PROCACHE_PATH", str(tmp_path / "provider.sqlite3"))

    class BombRequester:
        is_not_lazy = False
        auth = None
        base_url = "https://api.github.com"

        def requestJsonAndCheck(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError(f"N+1 HTTP completion forbidden during list: {args} {kwargs}")

    bomb = BombRequester()
    real_issue = Issue(
        bomb,
        {},
        {
            "number": 42,
            "title": "Real issue",
            "body": "Body text",
            "state": "closed",
            "state_reason": "completed",
            "html_url": "https://github.com/org/repo/issues/42",
            "url": "https://api.github.com/repos/org/repo/issues/42",
            "labels": [],
            "assignee": None,
            "updated_at": "2026-11-23T12:00:00Z",
        },
        completed=False,
    )
    real_pr = Issue(
        bomb,
        {},
        {
            "number": 43,
            "title": "Pull request item",
            "body": "PR body",
            "state": "open",
            "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/43"},
            "html_url": "https://github.com/org/repo/pull/43",
            "url": "https://api.github.com/repos/org/repo/issues/43",
            "labels": [],
            "assignee": None,
            "updated_at": "2026-11-23T12:00:00Z",
        },
        completed=False,
    )

    class FakeRepo:
        full_name = "org/repo"

        def get_issues(self, **kwargs):
            return [real_issue, real_pr]

    class FakeGithub:
        def __init__(self, auth_arg, **kwargs):
            self.requester = BombRequester()
            self._Github__requester = self.requester

        def get_repo(self, repo):
            return FakeRepo()

    monkeypatch.setattr("planfile.sync.github.Github", FakeGithub)
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-placeholder")
    backend = GitHubBackend("org/repo")
    tickets = backend.list_tickets()

    assert len(tickets) == 1
    assert tickets[0].id == "42"
    assert tickets[0].metadata["state_reason"] == "completed"


def _make_store(tmp_path):
    store = PlanfileStore(tmp_path)
    store.init()
    store.create_ticket(
        Ticket(
            id="PLF-001",
            name="Tracked issue",
            description="baseline",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={
                "github": {
                    "id": "101",
                    "url": "https://github.com/fixture/repo/issues/101",
                    "repository": "fixture/repo",
                }
            },
        )
    )
    return store


def _remote_issue(issue_id: str, description: str):
    return SimpleNamespace(
        id=issue_id,
        name="Tracked issue",
        description=description,
        status="open",
        assignee=None,
        labels=[],
        metadata={},
        key=None,
        url=f"https://github.com/fixture/repo/issues/{issue_id}",
    )


def test_incremental_cursor_flow_empty_delta_and_dry_run_isolation(tmp_path, monkeypatch):
    store = _make_store(tmp_path)
    seen_since: list[datetime | None] = []
    responses: list[list] = [
        [_remote_issue("101", "first remote pass")],
        [],
        [],
    ]

    class IncrementalBackend:
        config = {"repo": "fixture/repo"}

        def list_tickets(self, labels=None, status=None, assignee=None, limit=None, since=None):
            seen_since.append(since)
            return responses.pop(0)

    backend = IncrementalBackend()
    monkeypatch.delenv("PLANFILE_SYNC_FULL", raising=False)

    # First unscoped sync has no cursor yet -> since=None; writes inbound_cursor_at.
    sync_from_external(backend, store, False, "github")
    assert seen_since[0] is None
    state_file = tmp_path / ".planfile" / "sync" / "github.state.yaml"
    state_1 = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    cursor_1 = datetime.fromisoformat(state_1["inbound_cursor_at"])

    # Empty-delta dry_run=True must NOT touch github.state.yaml.
    raw_before_dry = state_file.read_text(encoding="utf-8")
    sync_from_external(backend, store, True, "github")
    assert seen_since[1] == cursor_1 - timedelta(seconds=60)
    assert state_file.read_text(encoding="utf-8") == raw_before_dry

    # Empty-delta dry_run=False MUST advance both synced_at and inbound_cursor_at.
    sync_from_external(backend, store, False, "github")
    assert seen_since[2] == cursor_1 - timedelta(seconds=60)
    state_2 = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(state_2["inbound_cursor_at"]) >= cursor_1
    assert state_2["synced_at"] >= state_1["synced_at"]


def test_scoped_sync_and_full_override_do_not_use_or_advance_cursor(tmp_path, monkeypatch):
    store = _make_store(tmp_path)
    seen_calls: list[dict] = []

    class RecordingBackend:
        config = {"repo": "fixture/repo"}

        def list_tickets(self, labels=None, status=None, assignee=None, limit=None, since=None):
            seen_calls.append({"labels": labels, "since": since})
            return [_remote_issue("101", "updated")]

        def list_selected_tickets(self, selected_remote_ids, labels=None):
            seen_calls.append({"selected": set(selected_remote_ids), "labels": labels})
            return [_remote_issue("101", "updated")]

    backend = RecordingBackend()
    monkeypatch.delenv("PLANFILE_SYNC_FULL", raising=False)
    sync_from_external(backend, store, False, "github")

    state_file = tmp_path / ".planfile" / "sync" / "github.state.yaml"
    state_after_full = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    cursor_before = state_after_full["inbound_cursor_at"]

    # Scoped by ticket_ids, remote_labels, or sprint_ids must not advance inbound_cursor_at or pass since.
    sync_from_external(backend, store, False, "github", ticket_ids=["PLF-001"])
    sync_from_external(backend, store, False, "github", remote_labels=["bug"])
    sync_from_external(backend, store, False, "github", sprint_ids=["backlog"])

    assert seen_calls[1] == {"selected": {"101"}, "labels": None}
    assert seen_calls[2] == {"labels": ["bug"], "since": None}
    assert seen_calls[3] == {"labels": None, "since": None}

    state_after_scoped = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    assert state_after_scoped["inbound_cursor_at"] == cursor_before

    # PLANFILE_SYNC_FULL=1 bypasses inbound_cursor_at while still updating it on completion.
    monkeypatch.setenv("PLANFILE_SYNC_FULL", "1")
    sync_from_external(backend, store, False, "github")
    assert seen_calls[4] == {"labels": None, "since": None}
    state_after_forced = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(state_after_forced["inbound_cursor_at"]) >= datetime.fromisoformat(cursor_before)
