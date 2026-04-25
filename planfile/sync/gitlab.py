import os
from typing import Any

try:
    import gitlab
    from gitlab.exceptions import GitlabError
except ImportError:
    gitlab = None
    GitlabError = None  # pip install python-gitlab

from planfile.sync.base import BasePMBackend, TicketRef, TicketState


class GitLabBackend(BasePMBackend):
    """GitLab Issues integration backend."""

    def __init__(
        self,
        url: str = "https://gitlab.com",
        token: str | None = None,
        project_id: int | None = None,
        **kwargs
    ):
        """
        Initialize GitLab backend.
        
        Args:
            url: GitLab instance URL (defaults to https://gitlab.com)
            token: GitLab token (defaults to GITLAB_TOKEN env var)
            project_id: Project ID (defaults to GITLAB_PROJECT_ID env var)
        """
        if gitlab is None:
            raise ImportError("python-gitlab is required. Install with: pip install python-gitlab")

        config = {
            "url": url,
            "token": token or os.environ.get("GITLAB_TOKEN"),
            "project_id": project_id or os.environ.get("GITLAB_PROJECT_ID"),
            **kwargs
        }
        super().__init__(config)

        self.gl = gitlab.Gitlab(self.config["url"], private_token=self.config["token"])
        self.project = self.gl.projects.get(int(self.config["project_id"]))

    def _validate_config(self) -> None:
        """Validate GitLab configuration."""
        if not self.config.get("token"):
            raise ValueError("GitLab token is required")

        if not self.config.get("project_id"):
            raise ValueError("GitLab project ID is required")

    def _prepare_labels(self, labels: list[str] | None, priority: str | None) -> list[str]:
        """Build label list, appending priority label."""
        issue_labels = list(labels or [])
        if priority:
            issue_labels.append(f"priority::{priority}")
        return issue_labels

    def _build_metadata_body(self, body: str, metadata: dict[str, Any] | None) -> str:
        """Append strategy metadata section to body."""
        if not metadata:
            return body
        metadata_section = "\n\n---\n\n### Strategy Metadata\n\n"
        for key, value in metadata.items():
            if key != "model_hints":
                metadata_section += f"- **{key}**: {value}\n"
        if "model_hints" in metadata:
            metadata_section += "\n### Model Hints\n\n"
            for phase, tier in metadata["model_hints"].items():
                if tier:
                    metadata_section += f"- **{phase}**: {tier}\n"
        return body + metadata_section

    def _create_ticket(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        backend_tag: str = "gitlab",
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TicketRef:
        """Create a new GitLab issue."""
        issue_labels = self._prepare_labels(labels, priority)
        body = self._build_metadata_body(body, metadata)

        try:
            issue = self.project.issues.create({
                "title": title,
                "description": body,
                "labels": issue_labels,
            })

            if assignee:
                users = self.gl.users.list(username=assignee)
                if users:
                    issue.assignee_id = users[0].id
                    issue.save()

            return self.build_ticket_ref(
                id=str(issue.iid),
                url=issue.web_url,
                key=f"Issue #{issue.iid}",
                status=issue.state,
                metadata=metadata,
            )
        except GitlabError as e:
            raise RuntimeError(f"Failed to create GitLab issue: {e}")

    def _update_labels(self, issue, labels: list[str] | None, priority: str | None) -> None:
        """Update issue labels, replacing priority labels."""
        current_labels = issue.labels
        current_labels = [l for l in current_labels if not l.startswith("priority::")]
        new_labels = list(labels or [])
        if priority:
            new_labels.append(f"priority::{priority}")
        issue.labels = current_labels + new_labels

    def _update_state(self, issue, status: str) -> None:
        """Update issue open/close state."""
        status_lower = status.lower()
        if status_lower == "closed":
            issue.state_event = "close"
        elif status_lower == "open":
            issue.state_event = "reopen"

    def _update_ticket(
        self,
        ticket_id: str,
        title: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        priority: str | None = None,
        backend_tag: str = "gitlab",
        assignee: str | None = None,
    ) -> None:
        """Update an existing GitLab issue."""
        try:
            issue = self.project.issues.get(ticket_id)

            if title:
                issue.title = title
            if body:
                issue.description = body
            if labels is not None or priority:
                self._update_labels(issue, labels, priority)
            if status:
                self._update_state(issue, status)
            if assignee:
                users = self.gl.users.list(username=assignee)
                if users:
                    issue.assignee_id = users[0].id

            issue.save()

        except GitlabError as e:
            raise RuntimeError(f"Failed to update GitLab issue {ticket_id}: {e}")

    def _get_ticket(self, ticket_id: str) -> TicketState:
        """Get GitLab issue status."""
        try:
            issue = self.project.issues.get(ticket_id)

            return self._issue_to_ticket_status(issue)
        except GitlabError as e:
            raise RuntimeError(f"Failed to get GitLab issue {ticket_id}: {e}")

    def _issue_to_ticket_status(self, issue) -> TicketState:
        """Convert a GitLab issue object into a TicketState."""
        return self.build_ticket_state(
            id=str(issue.iid),
            status=issue.state,
            assignee=issue.assignee["username"] if issue.assignee else None,
            labels=issue.labels or [],
            updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
        )

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        backend_tag: str = "gitlab",
        assignee: str | None = None,
        limit: int | None = None,
    ) -> list[TicketState]:
        """List GitLab issues with filters."""
        params = {}

        if labels:
            params["labels"] = ",".join(labels)

        if status:
            params["state"] = status.lower()

        if assignee:
            # Get user ID
            users = self.gl.users.list(username=assignee)
            if users:
                params["assignee_id"] = users[0].id

        try:
            issues = self.project.issues.list(**params, per_page=limit or 50)

            tickets = []
            for issue in issues:
                tickets.append(self._issue_to_ticket_status(issue))

            return tickets
        except GitlabError as e:
            raise RuntimeError(f"Failed to list GitLab issues: {e}")

    def _search_tickets(self, query: str) -> list[TicketState]:
        """Search GitLab issues."""
        try:
            issues = self.project.issues.list(search=query, state="all", per_page=50)

            tickets = []
            for issue in issues:
                tickets.append(self._issue_to_ticket_status(issue))

            return tickets
        except GitlabError as e:
            raise RuntimeError(f"Failed to search GitLab issues: {e}")
