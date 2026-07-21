"""OneDev Issues backend for Planfile-managed ticket queues."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from planfile.sync.base import BasePMBackend, TicketRef, TicketState


class OneDevError(RuntimeError):
    """Raised when the OneDev REST API rejects an operation."""


_DEDUP_MARKERS = (
    re.compile(r"<!--\s*planfile:deduplication-key=([^>]+?)\s*-->"),
    re.compile(r"<!--\s*ifuri-doctor:deduplication_key=([^>]+?)\s*-->"),
    re.compile(r"<!--\s*ifuri-doctor:fingerprint=([^>]+?)\s*-->"),
)


class OneDevBackend(BasePMBackend):
    """Create, read and transition OneDev Issues without involving GitHub."""

    DEFAULT_STATE_MAP = {
        "open": "Open",
        "in_progress": "In Progress",
        "review": "In Review",
        "done": "Closed",
        "closed": "Closed",
        "canceled": "Closed",
        "failed": "Open",
        "blocked": "Open",
    }
    DEFAULT_REVERSE_STATE_MAP = {
        "open": "open",
        "in progress": "in_progress",
        "in review": "review",
        "closed": "done",
    }

    def __init__(
        self,
        url: str,
        project: str,
        username: str | None = None,
        password: str | None = None,
        password_file: str | None = None,
        session: requests.Session | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_password = password or os.environ.get("ONEDEV_PASSWORD")
        configured_file = password_file or os.environ.get("ONEDEV_PASSWORD_FILE")
        if not resolved_password and configured_file:
            resolved_password = (
                Path(configured_file).expanduser().read_text(encoding="utf-8").strip()
            )
        config = {
            "url": url.rstrip("/"),
            "project": project,
            "username": username or os.environ.get("ONEDEV_USER"),
            "password": resolved_password,
            **kwargs,
        }
        super().__init__(config)
        self.session = session or requests.Session()
        self.session.auth = (self.config["username"], self.config["password"])
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self._project_cache: dict[str, Any] | None = None

    @property
    def publish_to(self) -> list[str]:
        value = self.config.get("publish_to") or []
        return [str(item) for item in value] if isinstance(value, list) else [str(value)]

    def _validate_config(self) -> None:
        if not self.config.get("url"):
            raise ValueError("OneDev URL is required")
        project = str(self.config.get("project", ""))
        if "/" not in project:
            raise ValueError("OneDev project must be in format 'owner/repository'")
        if not self.config.get("username") or not self.config.get("password"):
            raise ValueError("OneDev username and password are required")

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = self.session.request(
            method,
            f"{self.config['url']}{path}",
            json=payload,
            params=params,
            timeout=float(self.config.get("timeout", 30)),
        )
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            detail = getattr(response, "text", "")[-2000:]
            raise OneDevError(f"OneDev {method} {path} failed: {detail or exc}") from exc
        if not getattr(response, "content", b""):
            return None
        return response.json()

    def _projects(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._request("GET", "/~api/projects", params={"offset": offset, "count": 100})
            if not isinstance(page, list):
                raise OneDevError("OneDev projects endpoint returned a non-list response")
            rows.extend(page)
            if len(page) < 100:
                return rows
            offset += len(page)

    def _find_project(self, name: str, parent_id: int | None) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in self._projects()
                if row.get("name") == name and row.get("parentId") == parent_id
            ),
            None,
        )

    def _create_project(
        self, name: str, parent_id: int | None, *, code_management: bool
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "description": "Managed by Planfile",
            "codeManagement": code_management,
            "packManagement": False,
            "issueManagement": code_management,
            "timeTracking": False,
            "gitPackConfig": {},
            "codeAnalysisSetting": {},
        }
        if parent_id is not None:
            payload["parentId"] = parent_id
        result = self._request("POST", "/~api/projects", payload=payload)
        if isinstance(result, int):
            return {"id": result, "name": name, "parentId": parent_id}
        if isinstance(result, dict) and "id" in result:
            return result
        raise OneDevError("OneDev project creation returned an unsupported response")

    def _project(self) -> dict[str, Any]:
        if self._project_cache is not None:
            return self._project_cache
        owner, repository = self.config["project"].split("/", 1)
        parent = self._find_project(owner, None)
        if parent is None:
            parent = self._create_project(owner, None, code_management=False)
        project = self._find_project(repository, int(parent["id"]))
        if project is None:
            project = self._create_project(repository, int(parent["id"]), code_management=True)
        self._project_cache = project
        return project

    def _issues(self) -> list[dict[str, Any]]:
        project_id = int(self._project()["id"])
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._request(
                "GET",
                "/~api/issues",
                params={"withFields": "true", "offset": offset, "count": 100},
            )
            if not isinstance(page, list):
                raise OneDevError("OneDev issues endpoint returned a non-list response")
            rows.extend(row for row in page if int(row.get("projectId", -1)) == project_id)
            if len(page) < 100:
                return rows
            offset += len(page)

    @staticmethod
    def _deduplication_key(metadata: dict[str, Any] | None) -> str | None:
        metadata = metadata or {}
        for key in ("deduplication_key", "dedupe_key", "fingerprint", "planfile_id"):
            if metadata.get(key):
                return str(metadata[key]).strip()
        return None

    @staticmethod
    def _marker(key: str) -> str:
        safe_key = key.replace("-->", "").replace("\n", " ").strip()
        return f"<!-- planfile:deduplication-key={safe_key} -->"

    @classmethod
    def _extract_deduplication_key(cls, description: str) -> str | None:
        for pattern in _DEDUP_MARKERS:
            match = pattern.search(description or "")
            if match:
                return match.group(1).strip()
        return None

    def _issue_url(self, issue: dict[str, Any]) -> str:
        project = quote(self.config["project"], safe="/")
        return f"{self.config['url']}/{project}/~issues/{issue.get('number')}"

    def _issue_ref(
        self, issue: dict[str, Any], metadata: dict[str, Any] | None = None
    ) -> TicketRef:
        number = issue.get("number")
        return self.build_ticket_ref(
            id=str(issue["id"]),
            key=f"{self.config['project']}#{number}" if number is not None else None,
            url=self._issue_url(issue),
            status=self._normalize_state(str(issue.get("state", "Open"))),
            metadata={"number": number, **(metadata or {})},
        )

    def _create_ticket(
        self,
        name: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TicketRef:
        deduplication_key = self._deduplication_key(metadata)
        marker = self._marker(deduplication_key) if deduplication_key else None
        if marker:
            existing = next(
                (
                    row
                    for row in self._issues()
                    if self._extract_deduplication_key(str(row.get("description", "")))
                    == deduplication_key
                ),
                None,
            )
            if existing is not None:
                return self._issue_ref(existing, metadata)
            if marker not in body:
                body = f"{marker}\n{body}"

        fields = dict(self.config.get("fields") or {})
        if assignee and self.config.get("assignee_field"):
            fields[str(self.config["assignee_field"])] = [assignee]
        result = self._request(
            "POST",
            "/~api/issues",
            payload={
                "projectId": int(self._project()["id"]),
                "title": name,
                "description": body,
                "confidential": False,
                "iterationIds": [],
                "fields": fields,
            },
        )
        issue_id = int(result["id"]) if isinstance(result, dict) else int(result)
        issue = self._request("GET", f"/~api/issues/{issue_id}")
        return self._issue_ref(issue, metadata)

    def _update_ticket(
        self,
        ticket_id: str,
        title: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        name: str | None = None,
    ) -> None:
        issue = self._request("GET", f"/~api/issues/{int(ticket_id)}")
        resolved_title = name or title
        if resolved_title is not None and resolved_title != issue.get("title"):
            self._request("POST", f"/~api/issues/{int(ticket_id)}/title", payload=resolved_title)
        if body is not None and body != issue.get("description"):
            self._request("POST", f"/~api/issues/{int(ticket_id)}/description", payload=body)
        if status:
            target_state = self._onedev_state(status)
            if target_state != issue.get("state"):
                self._request(
                    "POST",
                    f"/~api/issues/{int(ticket_id)}/state-transitions",
                    payload={"state": target_state, "fields": {}, "comment": "Updated by Planfile"},
                )
        if assignee and self.config.get("assignee_field"):
            self._request(
                "POST",
                f"/~api/issues/{int(ticket_id)}/fields",
                payload={str(self.config["assignee_field"]): [assignee]},
            )

    def _get_ticket(self, ticket_id: str) -> TicketState:
        issue = self._request("GET", f"/~api/issues/{int(ticket_id)}")
        return self._issue_to_state(issue)

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
    ) -> list[TicketState]:
        tickets = [self._issue_to_state(issue) for issue in self._issues()]
        if status:
            tickets = [ticket for ticket in tickets if ticket.status == status]
        if labels:
            tickets = [ticket for ticket in tickets if set(labels).issubset(ticket.labels)]
        if assignee:
            tickets = [ticket for ticket in tickets if ticket.assignee == assignee]
        return tickets[:limit] if limit else tickets

    def _search_tickets(self, query: str) -> list[TicketState]:
        needle = query.lower()
        return [
            self._issue_to_state(issue)
            for issue in self._issues()
            if needle in str(issue.get("title", "")).lower()
            or needle in str(issue.get("description", "")).lower()
        ]

    def _onedev_state(self, status: str) -> str:
        state_map = {**self.DEFAULT_STATE_MAP, **(self.config.get("state_map") or {})}
        return str(state_map.get(status.lower(), status))

    def _normalize_state(self, state: str) -> str:
        reverse = dict(self.DEFAULT_REVERSE_STATE_MAP)
        reverse.update(
            {
                str(value).lower(): str(key)
                for key, value in (self.config.get("state_map") or {}).items()
            }
        )
        return reverse.get(state.lower(), state.lower().replace(" ", "_"))

    def _issue_to_state(self, issue: dict[str, Any]) -> TicketState:
        fields = {
            str(field.get("name")): field.get("value")
            for field in issue.get("fields", [])
            if isinstance(field, dict)
        }
        description = str(issue.get("description") or "")
        deduplication_key = self._extract_deduplication_key(description)
        labels = [f"onedev:{self.config['project']}"]
        if fields.get("Type"):
            labels.append(f"type:{fields['Type']}")
        if fields.get("Priority"):
            labels.append(f"priority:{str(fields['Priority']).lower()}")
        metadata = {
            "number": issue.get("number"),
            "project": self.config["project"],
            "source_backend": "onedev",
        }
        if deduplication_key:
            metadata["deduplication_key"] = deduplication_key
            metadata["fingerprint"] = deduplication_key
        return self.build_ticket_state(
            id=str(issue["id"]),
            key=f"{self.config['project']}#{issue.get('number')}",
            name=str(issue.get("title") or ""),
            description=description,
            url=self._issue_url(issue),
            status=self._normalize_state(str(issue.get("state", "Open"))),
            assignee=str(fields["Assignees"]) if fields.get("Assignees") else None,
            labels=labels,
            updated_at=(issue.get("lastActivity") or {}).get("date") or issue.get("submitDate"),
            metadata=metadata,
        )
