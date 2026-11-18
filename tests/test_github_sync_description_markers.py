"""Regression tests for per-issue marker isolation in GitHubBackend._list_tickets."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
import typer

from planfile.cli.groups.sync import core
from planfile.core.store import PlanfileStore, Ticket
from planfile.sync.github import GitHubBackend
from planfile.sync.operations import sync_from_external

START = GitHubBackend.DESCRIPTION_START
END = GitHubBackend.DESCRIPTION_END


class FakeIssue(SimpleNamespace):
    """Lightweight GitHub issue double tracking remote edits and state."""

    def __init__(
        self,
        number: int,
        *,
        title: str | None = None,
        body: str = "",
        state: str = "open",
        state_reason: str | None = None,
        labels: list[str] | None = None,
        pull_request: object = None,
    ):
        super().__init__(
            number=number,
            title=title or f"Issue {number}",
            body=body,
            state=state,
            state_reason=state_reason,
            html_url=f"https://github.com/owner/repo/issues/{number}",
            labels=[SimpleNamespace(name=label) for label in (labels or [])],
            assignee=None,
            updated_at=None,
            pull_request=pull_request,
            edits=[],
        )

    def edit(self, **fields):
        self.edits.append(fields)
        for key, value in fields.items():
            setattr(self, key, value)

    def set_labels(self, *labels):
        self.labels = [SimpleNamespace(name=label) for label in labels]


class FakeRepo:
    """In-memory repository double supporting listing, lookup, and creation."""

    full_name = "owner/repo"

    def __init__(self, issues: list[FakeIssue]):
        self.issues = list(issues)
        self.created: list[dict] = []

    def get_issues(self, **kwargs):
        state = kwargs.get("state", "all")
        required_labels = set(kwargs.get("labels") or ())
        results = []
        for issue in self.issues:
            if state != "all" and issue.state != state:
                continue
            issue_labels = {getattr(label, "name", str(label)) for label in (issue.labels or ())}
            if required_labels and not required_labels.issubset(issue_labels):
                continue
            results.append(issue)
        return results

    def get_issue(self, number: int):
        for issue in self.issues:
            if issue.number == number:
                return issue
        raise RuntimeError("404 Not Found")

    def get_labels(self):
        return []

    def create_label(self, **kwargs):
        pass

    def create_issue(self, **fields):
        self.created.append(fields)
        next_number = max((issue.number for issue in self.issues), default=0) + 1
        created = FakeIssue(
            next_number,
            title=fields["title"],
            body=fields["body"],
            labels=list(fields.get("labels") or []),
        )
        self.issues.append(created)
        return created


def make_backend(tmp_path, issues: list[FakeIssue]) -> GitHubBackend:
    """Construct a real GitHubBackend backed by FakeRepo."""
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "owner/repo", "cache_dir": str(tmp_path / "cache")}
    backend.repo = FakeRepo(issues)
    backend._mutation_interval = 0
    backend._last_mutation_at = 0
    backend._quarantined_inbound_issues = []
    backend._quarantined_inbound_count = 0
    return backend


def nested_legacy_body(secret_marker_text: str = "NESTED_SECRET_BODY_TOKEN") -> str:
    """Build a legacy nested duplicate planfile:description section (starts=2, ends=2)."""
    return (
        "<!-- planfile:deduplication-key=semcod/fixos:5f3864bb5d62d3dc:PLF-21821 -->\n"
        f"{START}\n"
        f"Outer section {secret_marker_text}\n"
        f"{START}\n"
        "Inner section\n"
        f"{END}\n"
        f"{END}\n"
    )


def test_list_tickets_quarantines_ambiguous_issues_without_starving_valid_results(
    tmp_path, caplog
):
    """Ambiguous markers isolate only offending issues in list_tickets while preserving strict paths."""
    valid_managed = FakeIssue(
        10,
        title="Valid managed",
        body=GitHubBackend._merge_description("remote note", "managed description"),
        state="open",
    )
    valid_unmarked = FakeIssue(
        11,
        title="Legacy unmarked",
        body="plain legacy description",
        state="open",
    )
    malformed_nested = FakeIssue(
        74,
        title="Legacy nested duplicate markers",
        body=nested_legacy_body("DO_NOT_LEAK_74"),
        state="closed",
        state_reason="completed",
    )
    malformed_sequential = FakeIssue(
        75,
        title="Legacy sequential duplicate markers",
        body=f"{START}\nfirst\n{END}\n\n{START}\nsecond DO_NOT_LEAK_75\n{END}",
        state="closed",
        state_reason="completed",
    )
    malformed_unclosed = FakeIssue(
        76,
        title="Unclosed start marker",
        body=f"{START}\nunclosed DO_NOT_LEAK_76",
        state="open",
    )
    valid_closed = FakeIssue(
        80,
        title="Valid closed issue",
        body=GitHubBackend._merge_description("", "finished work"),
        state="closed",
        state_reason="completed",
    )

    backend = make_backend(
        tmp_path,
        [
            valid_managed,
            malformed_nested,
            valid_unmarked,
            malformed_sequential,
            malformed_unclosed,
            valid_closed,
        ],
    )

    with caplog.at_level(logging.WARNING, logger="planfile.sync.github"):
        tickets = backend.list_tickets()

    assert [ticket.id for ticket in tickets] == ["10", "11", "80"]
    assert tickets[0].description == "managed description"
    assert tickets[1].description == "plain legacy description"
    assert tickets[2].description == "finished work"

    assert backend.quarantined_inbound_count == 3
    assert [entry["key"] for entry in backend.quarantined_inbound_issues] == [
        "owner/repo#74",
        "owner/repo#75",
        "owner/repo#76",
    ]
    assert all(
        entry["reason"] == "sync_github_description_markers_ambiguous"
        for entry in backend.quarantined_inbound_issues
    )
    for entry in backend.quarantined_inbound_issues:
        assert "body" not in entry
        assert "DO_NOT_LEAK" not in str(entry)
    assert "DO_NOT_LEAK" not in caplog.text

    # Quarantined issues do not consume limit slots.
    limited = backend.list_tickets(limit=2)
    assert [ticket.id for ticket in limited] == ["10", "11"]
    assert backend.quarantined_inbound_count == 1
    assert [entry["id"] for entry in backend.quarantined_inbound_issues] == ["74"]

    # Direct read, selected read, mutation, and search stay fail-closed.
    with pytest.raises(ValueError, match="sync_github_description_markers_ambiguous"):
        backend.get_ticket("74")
    with pytest.raises(ValueError, match="sync_github_description_markers_ambiguous"):
        backend.list_selected_tickets({"74"})
    with pytest.raises(ValueError, match="sync_github_description_markers_ambiguous"):
        backend.update_ticket("74", body="attempted overwrite", status="open")
    with pytest.raises(ValueError, match="sync_github_description_markers_ambiguous"):
        backend.search_tickets("Legacy nested")
    assert malformed_nested.edits == []


@pytest.mark.parametrize("sharded", [False, True])
def test_sync_from_external_survives_ambiguous_issue_and_recovers_after_repair(
    tmp_path, sharded
):
    """Inbound sync updates/imports valid issues and imports a previously malformed issue once fixed."""
    store = PlanfileStore(tmp_path)
    store.init()
    store.create_ticket(
        Ticket(
            id="PLF-010",
            name="Local title",
            description="stale description",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={"github": {"id": "10", "repository": "owner/repo"}},
        )
    )
    if sharded:
        store.migrate_to_sharded_yaml()

    repaired_target = FakeIssue(
        74,
        title="Legacy nested issue #74",
        body=nested_legacy_body(),
        state="closed",
        state_reason="completed",
    )
    issues = [
        FakeIssue(
            10,
            title="Remote #10",
            body=GitHubBackend._merge_description("discussion", "fresh accepted plan"),
            state="open",
        ),
        repaired_target,
        FakeIssue(
            80,
            title="New valid closed issue",
            body=GitHubBackend._merge_description("", "imported body"),
            state="closed",
            state_reason="completed",
        ),
    ]
    backend = make_backend(tmp_path, issues)

    sync_from_external(backend, store, False, "github")

    assert backend.quarantined_inbound_count == 1
    assert [entry["key"] for entry in backend.quarantined_inbound_issues] == ["owner/repo#74"]
    assert store.get_ticket("PLF-010").description == "fresh accepted plan"
    imported_80 = store.get_ticket("GITHUB-80")
    assert imported_80 is not None
    assert imported_80.status.value == "done"
    assert (
        imported_80.description.split("\n\n**Ticket impact radar (advisory)**", 1)[0]
        == "imported body"
    )
    assert store.get_ticket("GITHUB-74") is None

    # Repair issue #74 on GitHub; the next inbound pass clears quarantine and imports it.
    repaired_target.body = GitHubBackend._merge_description("", "repaired body")
    sync_from_external(backend, store, False, "github")

    assert backend.quarantined_inbound_count == 0
    assert backend.quarantined_inbound_issues == ()
    imported_74 = store.get_ticket("GITHUB-74")
    assert imported_74 is not None
    assert imported_74.status.value == "done"
    assert (
        imported_74.description.split("\n\n**Ticket impact radar (advisory)**", 1)[0]
        == "repaired body"
    )


def test_bidirectional_sync_completes_when_unmapped_issue_has_ambiguous_markers(tmp_path):
    """Bidirectional sync continues when an unmapped unrelated remote issue has ambiguous markers."""
    store = PlanfileStore(tmp_path)
    store.init()
    store.create_ticket(
        Ticket(
            id="PLF-010",
            name="Valid title",
            description="accepted plan",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={"github": {"id": "10", "repository": "owner/repo"}},
        )
    )
    desired_10 = store.get_ticket("PLF-010").description
    store.create_ticket(
        Ticket(
            id="PLF-099",
            name="Brand new local ticket",
            description="new work",
            status="open",
            sprint="backlog",
            integration=["github"],
        )
    )

    remote_10 = FakeIssue(
        10,
        title="Valid title",
        body=GitHubBackend._merge_description("", "stale remote"),
        state="open",
    )
    malformed_74 = FakeIssue(
        74,
        title="Unrelated corrupted legacy issue",
        body=nested_legacy_body(),
        state="closed",
        state_reason="completed",
    )
    backend = make_backend(tmp_path, [remote_10, malformed_74])
    tickets, _, source, data = core._load_tickets_for_sync(store, str(tmp_path), "github")

    core._execute_sync_with_progress(
        backend, tickets, False, store, "github", source, data, "both"
    )

    assert backend.quarantined_inbound_count == 1
    assert backend.get_ticket("10").description == desired_10
    assert store.get_ticket("PLF-099").sync["github"]["id"] == "75"
    assert malformed_74.edits == []


def test_bidirectional_sync_defers_mapped_quarantined_issue_without_mutating_remote(tmp_path):
    """A mapped ticket whose remote issue is quarantined stays deferred while valid tickets sync."""
    store = PlanfileStore(tmp_path)
    store.init()
    store.create_ticket(
        Ticket(
            id="PLF-010",
            name="Healthy ticket",
            description="desired 10",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={"github": {"id": "10", "repository": "owner/repo"}},
        )
    )
    desired_10 = store.get_ticket("PLF-010").description
    store.create_ticket(
        Ticket(
            id="PLF-074",
            name="Mapped corrupted ticket",
            description="desired 74",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={"github": {"id": "74", "repository": "owner/repo"}},
        )
    )

    remote_10 = FakeIssue(
        10,
        title="Healthy ticket",
        body=GitHubBackend._merge_description("", "stale 10"),
        state="open",
    )
    malformed_74 = FakeIssue(
        74,
        title="Mapped corrupted ticket",
        body=nested_legacy_body(),
        state="open",
    )
    backend = make_backend(tmp_path, [remote_10, malformed_74])
    tickets, _, source, data = core._load_tickets_for_sync(store, str(tmp_path), "github")

    with pytest.raises(typer.Exit) as caught:
        core._execute_sync_with_progress(
            backend, tickets, False, store, "github", source, data, "both"
        )

    assert caught.value.exit_code == 2
    assert backend.get_ticket("10").description == desired_10
    assert malformed_74.edits == []


def test_quarantine_diagnostics_are_bounded_and_non_marker_errors_propagate(tmp_path):
    """Quarantine storage is capped at MAX_QUARANTINED_INBOUND_ISSUES and other errors fail closed."""
    total_malformed = GitHubBackend.MAX_QUARANTINED_INBOUND_ISSUES + 6
    issues = [
        FakeIssue(i + 1, title=f"Bad {i + 1}", body=f"{START}\ndup\n{START}\n{END}")
        for i in range(total_malformed)
    ]
    issues.append(FakeIssue(999, title="Healthy", body="plain healthy body"))
    backend = make_backend(tmp_path, issues)

    listed = backend.list_tickets()
    assert [ticket.id for ticket in listed] == ["999"]
    assert backend.quarantined_inbound_count == total_malformed
    assert len(backend.quarantined_inbound_issues) == GitHubBackend.MAX_QUARANTINED_INBOUND_ISSUES

    store = PlanfileStore(tmp_path)
    store.init()
    failing_backend = make_backend(tmp_path, [FakeIssue(500, title="Exploding")])

    def raise_unexpected(_issue):
        raise ValueError("unexpected_issue_parse_error")

    failing_backend._issue_to_ticket_status = raise_unexpected
    with pytest.raises(RuntimeError, match="sync_inbound_fetch_failed") as exc_info:
        sync_from_external(failing_backend, store, False, "github")
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "unexpected_issue_parse_error"
