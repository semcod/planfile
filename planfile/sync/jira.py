import os
from typing import Any

try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    JIRA = None
    JIRAError = None  # pip install jira

from planfile.sync.base import BasePMBackend, TicketRef, TicketState


class JiraBackend(BasePMBackend):
    """Jira integration backend."""

    def __init__(
        self,
        base_url: str,
        email: str | None = None,
        token: str | None = None,
        project: str | None = None,
        **kwargs,
    ):
        """
        Initialize Jira backend.

        Args:
            base_url: Jira instance URL (e.g., "https://company.atlassian.net")
            email: Email for authentication (defaults to JIRA_EMAIL env var)
            token: API token (defaults to JIRA_TOKEN env var)
            project: Project key (defaults to JIRA_PROJECT env var)
        """
        if JIRA is None:
            raise ImportError("jira is required. Install with: pip install jira")

        config = {
            "base_url": base_url,
            "email": email or os.environ.get("JIRA_EMAIL"),
            "token": token or os.environ.get("JIRA_TOKEN"),
            "project": project or os.environ.get("JIRA_PROJECT"),
            **kwargs,
        }
        super().__init__(config)

        self.jira = JIRA(
            server=self.config["base_url"], basic_auth=(self.config["email"], self.config["token"])
        )

    def _validate_config(self) -> None:
        """Validate Jira configuration."""
        if not self.config.get("base_url"):
            raise ValueError("Jira base URL is required")

        if not self.config.get("email"):
            raise ValueError("Jira email is required")

        if not self.config.get("token"):
            raise ValueError("Jira token is required")

        if not self.config.get("project"):
            raise ValueError("Jira project key is required")

    def map_priority(self, priority: str | None) -> str:
        """Map generic priority to Jira Title Case priority."""
        if not priority:
            return "Medium"

        priority_map = self.config.get(
            "priority_map",
            {
                "lowest": "Lowest",
                "low": "Low",
                "medium": "Medium",
                "high": "High",
                "highest": "Highest",
            },
        )

        return priority_map.get(priority.lower(), "Medium")

    def _map_task_type_to_jira(self, task_type: str) -> str:
        """Map task type to Jira issue type."""
        type_map = self.config.get(
            "type_map",
            {
                "feature": "Story",
                "tech_debt": "Task",
                "bug": "Bug",
                "chore": "Task",
                "documentation": "Task",
            },
        )

        return type_map.get(task_type.lower(), "Task")

    def _build_metadata_section(self, metadata: dict[str, Any]) -> str:
        """Build a metadata section from metadata dict."""
        metadata_section = "\n\n---\n\n*Strategy Metadata:*\n"
        for key, value in metadata.items():
            if key not in ("model_hints", "type"):
                metadata_section += f"* {key}: {value}\n"

        if "model_hints" in metadata:
            metadata_section += "\n*Model Hints:*\n"
            for phase, tier in metadata["model_hints"].items():
                if tier:
                    metadata_section += f"* {phase}: {tier}\n"
        return metadata_section

    def _create_ticket(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        backend_tag: str = "jira",
    ) -> TicketRef:
        """Create a new Jira issue."""
        issue_dict = {
            "project": {"key": self.config["project"]},
            "summary": title,
            "description": body,
            "issuetype": {"name": "Task"},
        }

        if priority:
            issue_dict["priority"] = {"name": self.map_priority(priority)}

        if labels:
            issue_dict["labels"] = labels

        if metadata:
            issue_dict["description"] += self._build_metadata_section(metadata)
            if "type" in metadata:
                issue_dict["issuetype"] = {"name": self._map_task_type_to_jira(metadata["type"])}

        try:
            issue = self.jira.create_issue(fields=issue_dict)

            if assignee:
                self.jira.assign_issue(issue, assignee)

            return self.build_ticket_ref(
                id=issue.id,
                url=f"{self.config['base_url']}/browse/{issue.key}",
                key=issue.key,
                status=issue.fields.status.name,
                metadata=metadata,
            )
        except JIRAError as e:
            raise RuntimeError(f"Failed to create Jira issue: {e}") from e

    def _build_update_fields(
        self,
        title: str | None,
        body: str | None,
        priority: str | None,
        labels: list[str] | None,
    ) -> dict:
        """Build Jira update fields dict."""
        fields = {}
        if title:
            fields["summary"] = title
        if body:
            fields["description"] = body
        if priority:
            fields["priority"] = {"name": self.map_priority(priority)}
        if labels is not None:
            fields["labels"] = labels
        return fields

    def _transition_issue(self, issue, status: str) -> None:
        """Transition a Jira issue to the given status."""
        transitions = self.jira.transitions(issue)
        for transition in transitions:
            if transition["name"].lower() == status.lower():
                self.jira.transition_issue(issue, transition["id"])
                break

    def _update_ticket(
        self,
        ticket_id: str,
        name: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        *,
        backend_tag: str = "jira",
    ) -> None:
        """Update an existing Jira issue."""
        try:
            issue = self.jira.issue(ticket_id)

            fields = self._build_update_fields(name, body, priority, labels)
            if fields:
                issue.update(fields=fields)

            if status:
                self._transition_issue(issue, status)

            if assignee:
                self.jira.assign_issue(issue, assignee)

        except JIRAError as e:
            raise RuntimeError(f"Failed to update Jira issue {ticket_id}: {e}") from e

    def _get_ticket(self, ticket_id: str) -> TicketState:
        """Get Jira issue status."""
        try:
            issue = self.jira.issue(ticket_id)

            return self._issue_to_ticket_status(issue)
        except JIRAError as e:
            raise RuntimeError(f"Failed to get Jira issue {ticket_id}: {e}") from e

    def _issue_to_ticket_status(self, issue) -> TicketState:
        """Convert a Jira issue into a TicketState."""
        return self.build_ticket_state(
            id=issue.id,
            key=issue.key,
            status=issue.fields.status.name,
            assignee=issue.fields.assignee.displayName if issue.fields.assignee else None,
            labels=issue.fields.labels or [],
            updated_at=issue.fields.updated.isoformat() if issue.fields.updated else None,
        )

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
        *,
        backend_tag: str = "jira",
    ) -> list[TicketState]:
        """List Jira issues with filters."""
        jql = f"project = {self.config['project']}"

        if status:
            jql += f' AND status = "{status}"'

        if labels:
            for label in labels:
                jql += f' AND labels = "{label}"'

        if assignee:
            jql += f' AND assignee = "{assignee}"'

        jql += " ORDER BY updated DESC"

        try:
            issues = self.jira.search_issues(
                jql,
                maxResults=limit or 50,
                fields=["summary", "status", "assignee", "labels", "updated"],
            )

            tickets = []
            for issue in issues:
                tickets.append(self._issue_to_ticket_status(issue))

            return tickets
        except JIRAError as e:
            raise RuntimeError(f"Failed to list Jira issues: {e}") from e

    def _search_tickets(self, query: str, *, backend_tag: str = "jira") -> list[TicketState]:
        """Search Jira issues."""
        jql = f'project = {self.config["project"]} AND text ~ "{query}" ORDER BY updated DESC'

        try:
            issues = self.jira.search_issues(
                jql, maxResults=50, fields=["summary", "status", "assignee", "labels", "updated"]
            )

            tickets = []
            for issue in issues:
                tickets.append(self._issue_to_ticket_status(issue))

            return tickets
        except JIRAError as e:
            raise RuntimeError(f"Failed to search Jira issues: {e}") from e
