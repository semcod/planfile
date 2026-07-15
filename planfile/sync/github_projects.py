"""GitHub Projects v2 (org boards) integration for planfile.

Complements :class:`planfile.sync.github.GitHubBackend` (which handles Issues):
this backend adds an issue to an organization Project v2 board and sets a
single-select field (e.g. ``Status`` / ``Agent Status``). Token comes from the
``GITHUB_TOKEN`` environment variable by default, so it runs headless in CI.

Requires a token with the ``project`` scope (and ``repo`` for the issue). The
default GitHub Actions ``GITHUB_TOKEN`` cannot write org Projects — use a PAT or
GitHub App token.
"""
from __future__ import annotations

import os
from typing import Any

import requests

GRAPHQL_URL = "https://api.github.com/graphql"


class GitHubProjectsError(RuntimeError):
    """Raised when a Projects v2 GraphQL operation fails."""


class GitHubProjectsBackend:
    """Add issues to an org Project v2 board and set single-select fields."""

    def __init__(self, token: str | None = None, *, session: Any | None = None, timeout: int = 30) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token is required (pass token= or set GITHUB_TOKEN)")
        self._session = session or requests.Session()
        self._timeout = timeout

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self._session.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise GitHubProjectsError(str(payload["errors"]))
        return payload.get("data", {})

    def project_id(self, owner: str, number: int) -> str:
        data = self._graphql(
            "query($o:String!,$n:Int!){ organization(login:$o){ projectV2(number:$n){ id } } }",
            {"o": owner, "n": int(number)},
        )
        project = (data.get("organization") or {}).get("projectV2") or {}
        if not project.get("id"):
            raise GitHubProjectsError(f"Project {owner}#{number} not found or not accessible")
        return project["id"]

    def issue_node_id(self, owner: str, repo: str, number: int) -> str:
        data = self._graphql(
            "query($o:String!,$r:String!,$n:Int!){ repository(owner:$o,name:$r){ issue(number:$n){ id } } }",
            {"o": owner, "r": repo, "n": int(number)},
        )
        issue = ((data.get("repository") or {}).get("issue")) or {}
        if not issue.get("id"):
            raise GitHubProjectsError(f"Issue {owner}/{repo}#{number} not found")
        return issue["id"]

    def add_item(self, project_id: str, content_node_id: str) -> str:
        data = self._graphql(
            "mutation($p:ID!,$c:ID!){ addProjectV2ItemById(input:{projectId:$p,contentId:$c}){ item{ id } } }",
            {"p": project_id, "c": content_node_id},
        )
        return data["addProjectV2ItemById"]["item"]["id"]

    def single_select_field(self, project_id: str, name: str) -> dict[str, Any] | None:
        data = self._graphql(
            "query($p:ID!){ node(id:$p){ ... on ProjectV2{ fields(first:50){ nodes{"
            " ... on ProjectV2SingleSelectField{ id name options{ id name } } } } } } }",
            {"p": project_id},
        )
        nodes = (((data.get("node") or {}).get("fields")) or {}).get("nodes") or []
        for field in nodes:
            if field and field.get("name") == name:
                return field
        return None

    def set_single_select(self, project_id: str, item_id: str, field_id: str, option_id: str) -> None:
        self._graphql(
            "mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){ updateProjectV2ItemFieldValue(input:{"
            "projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){ projectV2Item{ id } } }",
            {"p": project_id, "i": item_id, "f": field_id, "o": option_id},
        )

    def add_issue(
        self,
        owner: str,
        number: int,
        content_node_id: str,
        *,
        status_field: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Add an issue (by node id) to the board; optionally set a single-select status.

        Returns ``{project_id, item_id, status_set, status_note}``. If the status
        field or option does not exist on the board, the item is still added and
        ``status_set`` is False with an explanatory note (no error).
        """
        project_id = self.project_id(owner, number)
        item_id = self.add_item(project_id, content_node_id)
        result: dict[str, Any] = {"project_id": project_id, "item_id": item_id, "status_set": False, "status_note": ""}
        if status_field and status:
            field = self.single_select_field(project_id, status_field)
            if field is None:
                result["status_note"] = f"field '{status_field}' not found on project"
            else:
                option = next((o for o in field.get("options", []) if o.get("name") == status), None)
                if option is None:
                    result["status_note"] = f"option '{status}' not found on field '{status_field}'"
                else:
                    self.set_single_select(project_id, item_id, field["id"], option["id"])
                    result["status_set"] = True
        return result
