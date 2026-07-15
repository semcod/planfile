from __future__ import annotations

import pytest

from planfile.sync import GitHubProjectsBackend, GitHubProjectsError


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    """Routes GraphQL queries to canned responses by matching the operation."""

    def __init__(self):
        self.calls = []

    def post(self, url, json, headers, timeout):  # noqa: A002 - mirrors requests API
        query = json["query"]
        self.calls.append(json)
        if "projectV2(number" in query:
            return _Resp({"data": {"organization": {"projectV2": {"id": "PROJ_1"}}}})
        if "issue(number" in query:
            return _Resp({"data": {"repository": {"issue": {"id": "ISSUE_NODE_1"}}}})
        if "addProjectV2ItemById" in query:
            return _Resp({"data": {"addProjectV2ItemById": {"item": {"id": "ITEM_1"}}}})
        if "ProjectV2SingleSelectField" in query:
            return _Resp(
                {"data": {"node": {"fields": {"nodes": [
                    {"id": "FIELD_STATUS", "name": "Status", "options": [
                        {"id": "OPT_TODO", "name": "Todo"}, {"id": "OPT_DONE", "name": "Done"},
                    ]},
                ]}}}}
            )
        if "updateProjectV2ItemFieldValue" in query:
            return _Resp({"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITEM_1"}}}})
        raise AssertionError(f"unexpected query: {query[:60]}")


def _backend():
    return GitHubProjectsBackend(token="t", session=_FakeSession())


def test_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError):
        GitHubProjectsBackend(token=None)


def test_resolve_ids():
    backend = _backend()
    assert backend.project_id("if-uri", 2) == "PROJ_1"
    assert backend.issue_node_id("if-uri", "repo-a", 5) == "ISSUE_NODE_1"


def test_add_issue_sets_known_status():
    backend = _backend()
    result = backend.add_issue("if-uri", 2, "ISSUE_NODE_1", status_field="Status", status="Todo")
    assert result["item_id"] == "ITEM_1"
    assert result["status_set"] is True


def test_add_issue_unknown_option_is_graceful():
    backend = _backend()
    result = backend.add_issue("if-uri", 2, "ISSUE_NODE_1", status_field="Status", status="Detected")
    assert result["item_id"] == "ITEM_1"
    assert result["status_set"] is False
    assert "option 'Detected'" in result["status_note"]


def test_add_issue_without_status():
    backend = _backend()
    result = backend.add_issue("if-uri", 2, "ISSUE_NODE_1")
    assert result["status_set"] is False
    assert result["status_note"] == ""


def test_graphql_errors_raise():
    class ErrSession:
        def post(self, *a, **k):
            return _Resp({"errors": [{"message": "boom"}]})

    backend = GitHubProjectsBackend(token="t", session=ErrSession())
    with pytest.raises(GitHubProjectsError):
        backend.project_id("if-uri", 2)
