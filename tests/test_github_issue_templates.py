"""Tests for GitHub issue template loading, rendering, readback, and safety guards."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from planfile.core.store import Store
from planfile.integrations.config import IntegrationConfig
from planfile.sync.github import GitHubBackend
from planfile.sync.outbound import sync_to_external


class _FakeIssue(SimpleNamespace):
    def edit(self, **fields):
        self.__dict__.update(fields)
        self.edits.append(fields)

    def set_labels(self, *labels):
        self.labels = [SimpleNamespace(name=label) for label in labels]


class _FakeRepo:
    full_name = "owner/repo"

    def __init__(self):
        self.issues: dict[int, _FakeIssue] = {}
        self.next_number = 100
        self.creates: list[dict] = []
        self.existing_labels: set[str] = {"planfile", "managed"}

    def get_labels(self):
        return [SimpleNamespace(name=name) for name in sorted(self.existing_labels)]

    def create_label(self, name: str, color: str = "0366d6", description: str = ""):
        self.existing_labels.add(name)
        return SimpleNamespace(name=name)

    def create_issue(self, **fields):
        self.creates.append(fields)
        self.next_number += 1
        number = self.next_number
        issue = _FakeIssue(
            number=number,
            html_url=f"https://github.com/owner/repo/issues/{number}",
            state="open",
            state_reason=None,
            title=fields["title"],
            body=fields["body"],
            assignee=fields.get("assignee"),
            labels=[SimpleNamespace(name=label) for label in fields.get("labels", [])],
            pull_request=None,
            updated_at=None,
            edits=[],
        )
        self.issues[number] = issue
        return issue

    def get_issue(self, number: int):
        return self.issues[number]

    def get_issues(self, **_kwargs):
        return list(self.issues.values())


def _backend(config: dict | None = None) -> GitHubBackend:
    backend = GitHubBackend.__new__(GitHubBackend)
    backend.config = {"repo": "owner/repo", **(config or {})}
    backend.repo = _FakeRepo()
    backend._label_names = {"planfile", "managed"}
    backend._last_mutation_at = 0.0
    backend._mutation_interval = 0.0
    backend._creation_lock = lambda _key=None: nullcontext()
    backend._find_issue_by_markers = lambda _markers: None
    backend._cache_marker_result = lambda *_args: None
    backend._clear_read_cache = lambda: None
    backend._throttle_mutation = lambda: None
    return backend


def test_inline_template_preserves_json_braces_and_description_tokens():
    backend = _backend({
        "issue_template": (
            "Ticket {id} ({priority}) - {title}\n\n"
            "Payload sample: {\"a\": 1}\n\n"
            "{description}"
        )
    })
    ref = backend.create_ticket({
        "id": "PLF-12",
        "name": "Handle braces",
        "priority": "high",
        "status": "open",
        "description": "Verbatim {id} and {\"nested\": 2}",
    })

    issue = backend.repo.get_issue(int(ref.id))
    assert "Ticket PLF-12 (high) - Handle braces" in issue.body
    assert 'Payload sample: {"a": 1}' in issue.body
    assert issue.body.count(GitHubBackend.DESCRIPTION_START) == 1
    assert issue.body.count(GitHubBackend.DESCRIPTION_END) == 1
    assert backend.get_ticket(ref.id).description == 'Verbatim {id} and {"nested": 2}'


def test_integration_config_resolves_markdown_template_from_different_cwd(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    (project_dir / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
    (project_dir / ".planfile").mkdir(parents=True)
    (project_dir / ".planfile" / "sync.planfile.yaml").write_text(
        "integrations:\n"
        "  github:\n"
        "    repo: owner/repo\n"
        "    token: dummy-token\n"
        f"    cache_path: {tmp_path / 'procache.sqlite3'}\n"
        f"    cache_dir: {tmp_path / 'gh_cache'}\n"
        "    default_labels: [triage]\n"
        "    issue_template: bug_report\n",
        encoding="utf-8",
    )
    (project_dir / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").write_text(
        "---\n"
        "name: Bug report\n"
        "title: \"[Bug]: Default bug\"\n"
        "labels: bug, needs-info\n"
        "assignees:\n"
        "  - alice\n"
        "---\n"
        "### Bug Summary\n\n"
        "{description}\n\n"
        "### Priority\n"
        "{priority}\n",
        encoding="utf-8",
    )

    other_cwd = tmp_path / "elsewhere"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    def _request_json_and_check(_method: str, _url: str):
        return {}, {"id": 4242, "full_name": "owner/repo"}

    fake_repo = _FakeRepo()
    fake_github = SimpleNamespace(
        requester=SimpleNamespace(
            base_url="https://api.github.com",
            requestJsonAndCheck=_request_json_and_check,
        ),
        get_repo=lambda _repo: fake_repo,
    )
    with patch("planfile.sync.github.Github", return_value=fake_github):
        cfg = IntegrationConfig(str(project_dir))
        cfg.load_configs()
        backend = cfg.get_integration_backend("github")

    assert backend.config["project_dir"] == str(project_dir)
    backend._identity_requester = None
    backend._creation_lock = lambda _key=None: nullcontext()
    backend._find_issue_by_markers = lambda _markers: None
    backend._cache_marker_result = lambda *_args: None
    backend._clear_read_cache = lambda: None
    backend._throttle_mutation = lambda: None
    backend._label_names = {"planfile", "managed"}

    store = Store(project_dir)
    store.init()
    ticket = {
        "id": "PLF-44",
        "name": "Crash on save",
        "description": "Stack trace here",
        "priority": "high",
        "status": "open",
        "integration": ["github"],
    }
    result = sync_to_external(backend, [("PLF-44", ticket)], False, store, "github")
    assert result.created == ("PLF-44",)

    issue = fake_repo.get_issue(101)
    assert issue.title == "Crash on save"
    assert issue.assignee == "alice"
    assert [label.name for label in issue.labels] == [
        "triage",
        "bug",
        "needs-info",
        "priority-high",
        "planfile",
        "managed",
    ]
    assert "### Bug Summary" in issue.body
    assert backend.get_ticket("101").description == "Stack trace here"

    untitled = backend.create_ticket({
        "id": "PLF-45",
        "name": "",
        "description": "Missing title fallback",
        "status": "open",
    })
    assert fake_repo.get_issue(int(untitled.id)).title == "[Bug]: Default bug"


def test_yaml_issue_form_renders_sections_and_embeds_managed_description(tmp_path):
    (tmp_path / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
    (tmp_path / ".github" / "ISSUE_TEMPLATE" / "feature.yml").write_text(
        "name: Feature Request\n"
        "description: Propose a feature\n"
        "labels: [enhancement, intake]\n"
        "assignees: [bob]\n"
        "body:\n"
        "  - type: markdown\n"
        "    attributes:\n"
        "      value: Thanks for proposing a change!\n"
        "  - type: dropdown\n"
        "    id: component\n"
        "    attributes:\n"
        "      label: Component\n"
        "      options: [CLI, API]\n"
        "      default: 1\n"
        "  - type: textarea\n"
        "    id: summary\n"
        "    attributes:\n"
        "      label: Problem Statement\n"
        "  - type: checkboxes\n"
        "    id: checks\n"
        "    attributes:\n"
        "      label: Confirmation\n"
        "      options:\n"
        "        - label: I checked existing issues\n",
        encoding="utf-8",
    )

    backend = _backend({
        "project_dir": str(tmp_path),
        "issue_template": ".github/ISSUE_TEMPLATE/feature.yml",
    })
    ref = backend.create_ticket({
        "id": "PLF-77",
        "name": "Support YAML forms",
        "description": "Add issue form rendering",
        "status": "open",
        "metadata": {"component": "CLI"},
    })

    issue = backend.repo.get_issue(int(ref.id))
    assert "Thanks for proposing a change!" in issue.body
    assert "### Component\n\nCLI" in issue.body
    assert "### Problem Statement\n\n" in issue.body
    assert "### Confirmation\n\n- [ ] I checked existing issues" in issue.body
    assert issue.body.count(GitHubBackend.DESCRIPTION_START) == 1
    assert backend.get_ticket(ref.id).description == "Add issue form rendering"
    assert [label.name for label in issue.labels] == [
        "enhancement",
        "intake",
        "planfile",
        "managed",
    ]


def test_template_without_description_placeholder_and_roundtrip_update(tmp_path):
    store = Store(tmp_path)
    store.init()
    backend = _backend({
        "issue_template": "## Standard Header\n\nTicket: {id}\n\n## Checklist\n- [ ] Triaged"
    })
    ticket = {
        "id": "PLF-88",
        "name": "Roundtrip template",
        "description": "Initial details",
        "status": "open",
        "integration": ["github"],
    }

    created = sync_to_external(backend, [("PLF-88", ticket)], False, store, "github")
    assert created.created == ("PLF-88",)
    issue = backend.repo.get_issue(101)
    assert "## Standard Header" in issue.body
    assert "## Checklist" in issue.body
    assert backend.get_ticket("101").description == "Initial details"

    ticket["description"] = "Updated details"
    updated = sync_to_external(backend, [("PLF-88", ticket)], False, store, "github")
    assert updated.updated == ("PLF-88",)
    assert "## Standard Header" in issue.body
    assert "## Checklist" in issue.body
    assert issue.body.count(GitHubBackend.DESCRIPTION_START) == 1
    assert backend.get_ticket("101").description == "Updated details"


def test_auto_template_lookup_single_and_ambiguous(tmp_path):
    tmpl_dir = tmp_path / ".github" / "ISSUE_TEMPLATE"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "config.yml").write_text("blank_issues_enabled: false\n", encoding="utf-8")
    (tmpl_dir / "only.md").write_text("Auto template: {description}\n", encoding="utf-8")

    backend = _backend({"project_dir": str(tmp_path), "issue_template": "auto"})
    ref = backend.create_ticket({
        "id": "PLF-90",
        "name": "Auto template",
        "description": "Picked automatically",
        "status": "open",
    })
    assert "Auto template:" in backend.repo.get_issue(int(ref.id)).body

    (tmpl_dir / "second.md").write_text("Second: {description}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sync_github_issue_template_ambiguous"):
        backend.preflight([("PLF-91", {"status": "open"})])
    assert len(backend.repo.creates) == 1


def test_duplicate_description_placeholders_emit_one_managed_region():
    backend = _backend({
        "issue_template": "Primary:\n{description}\n\nMirror:\n{body}"
    })
    ref = backend.create_ticket({
        "id": "PLF-95",
        "name": "Single markers",
        "description": "Important body",
        "status": "open",
    })
    issue = backend.repo.get_issue(int(ref.id))
    assert issue.body.count(GitHubBackend.DESCRIPTION_START) == 1
    assert issue.body.count(GitHubBackend.DESCRIPTION_END) == 1
    assert backend.get_ticket(ref.id).description == "Important body"


def test_fail_closed_on_missing_traversal_symlink_and_invalid_labels_in_preflight(tmp_path):
    outside = tmp_path / "secret.md"
    outside.write_text("secret", encoding="utf-8")
    project_dir = tmp_path / "project"
    (project_dir / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)

    missing_backend = _backend({
        "project_dir": str(project_dir),
        "issue_template": ".github/ISSUE_TEMPLATE/missing.md",
    })
    with pytest.raises(ValueError, match="sync_github_issue_template_not_found"):
        missing_backend.preflight([("PLF-1", {"status": "open"})])
    with pytest.raises(ValueError, match="sync_github_issue_template_not_found"):
        missing_backend.create_ticket({"id": "PLF-1", "name": "x", "status": "open"})
    assert missing_backend.repo.creates == []

    traversal_backend = _backend({
        "project_dir": str(project_dir),
        "issue_template": "../secret.md",
    })
    with pytest.raises(ValueError, match="sync_github_issue_template_invalid"):
        traversal_backend.preflight([("PLF-1", {"status": "open"})])
    assert traversal_backend.repo.creates == []

    link = project_dir / ".github" / "ISSUE_TEMPLATE" / "escape.md"
    link.symlink_to(outside)
    symlink_backend = _backend({
        "project_dir": str(project_dir),
        "issue_template": ".github/ISSUE_TEMPLATE/escape.md",
    })
    with pytest.raises(ValueError, match="sync_github_issue_template_invalid"):
        symlink_backend.preflight([("PLF-1", {"status": "open"})])
    assert symlink_backend.repo.creates == []

    bad_label_file = project_dir / ".github" / "ISSUE_TEMPLATE" / "bad_label.md"
    bad_label_file.write_text(
        f"---\nlabels: [{'x' * (GitHubBackend.MAX_LABEL_LENGTH + 1)}]\n---\n{{description}}\n",
        encoding="utf-8",
    )
    bad_label_backend = _backend({
        "project_dir": str(project_dir),
        "issue_template": "bad_label",
    })
    with pytest.raises(ValueError, match="Invalid GitHub label"):
        bad_label_backend.preflight([("PLF-1", {"status": "open"})])
    assert bad_label_backend.repo.creates == []
