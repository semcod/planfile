from __future__ import annotations

from pathlib import Path

import yaml

from planfile.testql_integration import (
    _resolve_testql_executable,
    build_testql_tickets,
    sync_testql_tickets,
    upsert_testql_tickets,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_testql_tickets_from_failed_report() -> None:
    report = {
        "ok": False,
        "failed": 2,
        "errors": [
            "GET /api/users expected 200 got 500 in src/api/users.py",
            "Button #save failed assertion",
        ],
    }

    tickets = build_testql_tickets(report, "tests/api.testql.toon.yaml", max_tickets=10)

    assert len(tickets) == 2
    assert tickets[0]["id"].startswith("TQL-")
    assert tickets[0]["action"] == "fix"
    assert tickets[0]["status"] == "todo"
    assert "testql" in tickets[0]["labels"]
    assert tickets[0]["file"] == "src/api/users.py"


def test_build_testql_tickets_handles_compact_report_steps_count() -> None:
    report = {
        "ok": False,
        "failed": 1,
        "steps": 6,
        "errors": "Connection refused",
    }

    tickets = build_testql_tickets(report, "tests/api.testql.toon.yaml", max_tickets=10)

    assert len(tickets) == 1
    assert tickets[0]["id"].startswith("TQL-")


def test_upsert_testql_tickets_updates_tasks_and_sprint_patterns(tmp_path: Path) -> None:
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "tasks": [{"id": "Q01", "title": "Existing task"}],
                "sprints": [
                    {
                        "id": "sprint-1",
                        "name": "Main",
                        "task_patterns": [{"id": "Q01", "name": "Existing task"}],
                    }
                ],
            },
            sort_keys=False,
        ),
    )

    tickets = [
        {
            "id": "TQL-a1",
            "title": "testql failure A",
            "description": "desc A",
            "action": "fix",
            "priority": 2,
            "status": "todo",
            "labels": ["testql"],
        },
        {
            "id": "TQL-a1",
            "title": "testql failure A duplicate",
            "description": "desc A",
            "action": "fix",
            "priority": 2,
            "status": "todo",
            "labels": ["testql"],
        },
    ]

    report = upsert_testql_tickets(strategy_path, tickets, project_path=tmp_path)

    assert report["created"] == 1
    assert report["skipped"] == 1

    data = yaml.safe_load(strategy_path.read_text(encoding="utf-8"))
    task_ids = {task["id"] for task in data["tasks"]}
    pattern_ids = {task["id"] for task in data["sprints"][0]["task_patterns"]}

    assert "TQL-a1" in task_ids
    assert "TQL-a1" in pattern_ids


def test_upsert_testql_tickets_deduplicates_by_external_url(tmp_path: Path) -> None:
    strategy_path = tmp_path / "planfile.yaml"
    _write(
        strategy_path,
        yaml.safe_dump(
            {
                "tasks": [
                    {
                        "id": "GH-1",
                        "title": "existing",
                        "external_url": "https://gitlab.com/group/project/-/issues/123/",
                    }
                ],
                "sprints": [{"id": "sprint-1", "name": "Main", "task_patterns": []}],
            },
            sort_keys=False,
        ),
    )

    tickets = [
        {
            "id": "TQL-new",
            "title": "duplicate by url",
            "description": "d",
            "external_url": "https://gitlab.com/group/project/-/issues/123",
            "labels": ["testql"],
        }
    ]

    report = upsert_testql_tickets(strategy_path, tickets, project_path=tmp_path)

    assert report["created"] == 0
    assert report["skipped"] == 1


class _FakeBackend:
    def __init__(self, name: str, bucket: list[tuple[str, str]]):
        self._name = name
        self._bucket = bucket

    def create_ticket(self, ticket: dict) -> None:
        self._bucket.append((self._name, ticket.get("id") or ticket.get("title") or ticket.get("name", "")))


class _UpdateAwareBackend:
    def __init__(self, search_results: list[dict] | None = None):
        self.created: list[str] = []
        self.updated: list[str] = []
        self.searched: list[str] = []
        self.search_results = search_results or []

    def create_ticket(self, ticket: dict) -> dict:
        self.created.append(ticket.get("id") or "")
        return {"id": "C-1", "url": "https://example.local/issues/C-1"}

    def update_ticket(self, ticket_id: str, **_kwargs) -> None:
        self.updated.append(ticket_id)

    def search_tickets(self, query: str) -> list[dict]:
        self.searched.append(query)
        return self.search_results


def test_sync_testql_tickets_runs_markdown_first(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class _FakeIntegrationConfig:
        def __init__(self, directory: str):
            self.directory = directory
            self.config = {"integrations": {"github": {"repo": "a/b"}, "jira": {"url": "x", "project": "Y"}}}

        def load_configs(self) -> None:
            return None

        def validate_integration(self, name: str) -> bool:
            return name in {"github", "jira"}

        def get_default_backend(self) -> _FakeBackend:
            return _FakeBackend("markdown", calls)

        def get_integration_backend(self, integration_name: str) -> _FakeBackend:
            return _FakeBackend(integration_name, calls)

    monkeypatch.setattr("planfile.testql_integration.IntegrationConfig", _FakeIntegrationConfig)

    tickets = [
        {"id": "TQL-a", "title": "A", "description": "d", "labels": ["testql"], "priority": "high"},
        {"id": "TQL-b", "title": "B", "description": "d", "labels": ["testql"], "priority": "high"},
    ]

    report = sync_testql_tickets(tickets, project_path=tmp_path)

    assert report["sync_order"] == ["markdown", "github", "jira"]
    assert calls[:2] == [("markdown", "TQL-a"), ("markdown", "TQL-b")]


def test_sync_testql_tickets_updates_by_external_id(tmp_path: Path, monkeypatch) -> None:
    backend = _UpdateAwareBackend()

    class _FakeIntegrationConfig:
        def __init__(self, directory: str):
            self.directory = directory
            self.config = {"integrations": {}}

        def load_configs(self) -> None:
            return None

        def get_default_backend(self) -> _UpdateAwareBackend:
            return backend

    monkeypatch.setattr("planfile.testql_integration.IntegrationConfig", _FakeIntegrationConfig)

    tickets = [
        {
            "id": "TQL-a",
            "title": "A",
            "description": "d",
            "external_refs": [{"integration": "markdown", "id": "42"}],
        }
    ]

    report = sync_testql_tickets(tickets, project_path=tmp_path, include_configured=False)

    assert report["integrations"][0]["integration"] == "markdown"
    assert report["integrations"][0]["updated"] == 1
    assert backend.updated == ["42"]
    assert backend.created == []
    assert tickets[0]["markdown_id"] == "42"


def test_sync_testql_tickets_updates_by_url_search(tmp_path: Path, monkeypatch) -> None:
    backend = _UpdateAwareBackend(search_results=[{"id": "77"}])

    class _FakeIntegrationConfig:
        def __init__(self, directory: str):
            self.directory = directory
            self.config = {"integrations": {}}

        def load_configs(self) -> None:
            return None

        def get_default_backend(self) -> _UpdateAwareBackend:
            return backend

    monkeypatch.setattr("planfile.testql_integration.IntegrationConfig", _FakeIntegrationConfig)

    tickets = [
        {
            "id": "TQL-a",
            "title": "A",
            "description": "d",
            "external_refs": [{"integration": "markdown", "url": "https://example.local/issues/77"}],
        }
    ]

    report = sync_testql_tickets(tickets, project_path=tmp_path, include_configured=False)

    assert report["integrations"][0]["updated"] == 1
    assert backend.searched == ["https://example.local/issues/77"]
    assert backend.updated == ["77"]
    assert backend.created == []


def test_resolve_testql_executable_falls_back_to_local_repo(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "testql"
    bin_path = repo / ".venv" / "bin"
    bin_path.mkdir(parents=True, exist_ok=True)
    executable = bin_path / "testql"
    executable.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")

    monkeypatch.setattr("planfile.testql_integration.shutil.which", lambda _name: None)

    resolved = _resolve_testql_executable("testql", repo)

    assert resolved == str(executable)
