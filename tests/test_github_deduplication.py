from __future__ import annotations

from types import SimpleNamespace

from planfile.sync.github import GitHubBackend
from planfile.sync.operations import _backend_ticket_payload


class FakeRepo:
    full_name = "subactor/doctor-agent"

    def __init__(self, issues):
        self.issues = issues
        self.created = []

    def get_labels(self):
        return []

    def create_label(self, **kwargs):
        return None

    def get_issues(self, **kwargs):
        return self.issues

    def create_issue(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(number=99, html_url="https://github/99", state="open")


def test_github_reuses_legacy_doctor_fingerprint_instead_of_creating_duplicate():
    issue = SimpleNamespace(
        number=7,
        html_url="https://github/7",
        state="open",
        body="<!-- ifuri-doctor:fingerprint=doctor:abc -->\nold evidence",
    )
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "subactor/doctor-agent"}
    backend.repo = FakeRepo([issue])

    result = backend._create_ticket(
        "Doctor finding",
        "<!-- ifuri-doctor:fingerprint=doctor:abc -->\nnew evidence",
        metadata={"deduplication_key": "doctor:abc"},
    )

    assert result.id == "7"
    assert backend.repo.created == []


def test_planfile_id_marker_is_scoped_to_target_repository():
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "owner/repo"}
    backend.repo = SimpleNamespace(full_name="owner/repo")

    body = backend._build_metadata_body("evidence", {"planfile_id": "PLF-2"})

    assert "planfile:deduplication-key=owner/repo:PLF-2" in body


def test_same_local_id_from_two_stores_gets_distinct_markers():
    ticket = {"name": "independent", "description": "evidence"}
    first = _backend_ticket_payload(ticket, "PLF-2", "owner/repo", "store-a")
    second = _backend_ticket_payload(ticket, "PLF-2", "owner/repo", "store-b")

    assert first["metadata"]["planfile_id"] != second["metadata"]["planfile_id"]


def test_terminal_planfile_status_closes_github_issue():
    class FakeIssue:
        def __init__(self):
            self.edits = []

        def edit(self, **kwargs):
            self.edits.append(kwargs)

    backend = GitHubBackend.__new__(GitHubBackend)
    issue = FakeIssue()

    for status in ("done", "completed", "closed", "canceled", "cancelled"):
        backend._update_issue_state(issue, status)

    assert issue.edits == [{"state": "closed"}] * 5


def test_non_terminal_planfile_status_keeps_github_issue_open():
    class FakeIssue:
        def __init__(self):
            self.edits = []

        def edit(self, **kwargs):
            self.edits.append(kwargs)

    backend = GitHubBackend.__new__(GitHubBackend)
    issue = FakeIssue()

    for status in ("open", "triage", "in_progress", "in-progress"):
        backend._update_issue_state(issue, status)

    assert issue.edits == [{"state": "open"}] * 4
