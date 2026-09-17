"""An outbound sync must not delete or resurrect what a tracker already holds.

`semcod/fixos#46` lost 28 lines of evidence and a dated title on 2026-09-16,
when a sync replaced its body with the ticket description. The issue state is a
separate question, recorded in #125: the reopen that resurrected
`subactor/onedev-agent#395` is asserted deliberately by ticket-101's routing
tests, so it is the owner's call and not changed here.
"""

from __future__ import annotations

from types import SimpleNamespace

from planfile.sync.github import GitHubBackend


class FakeIssue(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(edits=[], **kwargs)

    def edit(self, **kwargs):
        self.edits.append(kwargs)
        if "body" in kwargs:
            self.body = kwargs["body"]
        if "title" in kwargs:
            self.title = kwargs["title"]
        if "state" in kwargs:
            self.state = kwargs["state"]


class FakeRepo:
    full_name = "semcod/fixos"

    def __init__(self, issue):
        self.issue = issue

    def get_issue(self, number):
        return self.issue

    def get_labels(self):
        return []


def _backend(issue: FakeIssue) -> GitHubBackend:
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "semcod/fixos"}
    backend.repo = FakeRepo(issue)
    return backend


EVIDENCE = (
    "<!-- planfile:deduplication-key=DFU0915-001 -->\n"
    "## Kontekst\n\n"
    "`uv lock --check`: exit 0 on 5016406^, exit 1 on main.\n\n"
    "## Blokery\n\n- GOV-WORKSTREAM-002\n"
)


def test_update_keeps_the_issue_body_and_owns_only_its_section():
    issue = FakeIssue(number=46, title="Kontynuacja 2026-09-15: relock uv.lock", state="open", body=EVIDENCE)

    _backend(issue)._update_ticket("46", name="Kontynuacja: relock uv.lock", body="Planning-only record.")

    assert "## Kontekst" in issue.body
    assert "GOV-WORKSTREAM-002" in issue.body
    assert "<!-- planfile:deduplication-key=DFU0915-001 -->" in issue.body
    assert GitHubBackend.DESCRIPTION_START in issue.body
    assert "Planning-only record." in issue.body
    # A rename is a deliberate action on the issue, not a sync side effect.
    assert issue.title == "Kontynuacja 2026-09-15: relock uv.lock"
    assert all("title" not in edit for edit in issue.edits)


def test_second_update_replaces_the_section_without_stacking_it():
    issue = FakeIssue(number=46, title="t", state="open", body=EVIDENCE)
    backend = _backend(issue)

    backend._update_ticket("46", body="first")
    backend._update_ticket("46", body="second")

    assert issue.body.count(GitHubBackend.DESCRIPTION_START) == 1
    assert "second" in issue.body
    assert "first" not in issue.body
    assert "## Kontekst" in issue.body


def test_update_writes_nothing_when_the_body_already_matches():
    issue = FakeIssue(number=46, title="t", state="open", body=EVIDENCE)
    backend = _backend(issue)

    backend._update_ticket("46", body="same")
    edits_after_first = len(issue.edits)
    backend._update_ticket("46", body="same")

    assert len(issue.edits) == edits_after_first


def test_an_empty_issue_body_becomes_just_the_section():
    issue = FakeIssue(number=7, title="t", state="open", body=None)

    _backend(issue)._update_ticket("7", body="only record")

    assert issue.body == f"{GitHubBackend.DESCRIPTION_START}\nonly record\n{GitHubBackend.DESCRIPTION_END}"
