from __future__ import annotations

from types import SimpleNamespace

from planfile.sync.github import GitHubBackend


class FakeRepo:
    full_name = "if-uri/doctor-agent"

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
    backend.config = {"repo": "if-uri/doctor-agent"}
    backend.repo = FakeRepo([issue])

    result = backend._create_ticket(
        "Doctor finding",
        "<!-- ifuri-doctor:fingerprint=doctor:abc -->\nnew evidence",
        metadata={"deduplication_key": "doctor:abc"},
    )

    assert result.id == "7"
    assert backend.repo.created == []
