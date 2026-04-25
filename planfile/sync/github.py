import os
from typing import Any

try:
    from github import Github
    from github.Issue import Issue
    from github.Repository import Repository
except ImportError:
    Github = None
    Issue = None
    Repository = None  # pip install PyGithub

from planfile.sync.base import BasePMBackend, TicketRef, TicketState


class GitHubBackend(BasePMBackend):
    """GitHub Issues integration backend."""

    def __init__(self, repo: str, token: str | None = None, **kwargs):
        """
        Initialize GitHub backend.
        
        Args:
            repo: Repository in format "owner/repo"
            token: GitHub token (defaults to GITHUB_TOKEN env var)
        """
        if Github is None:
            raise ImportError("PyGithub is required. Install with: pip install PyGithub")

        config = {
            "repo": repo,
            "token": token or os.environ.get("GITHUB_TOKEN"),
            **kwargs
        }
        super().__init__(config)

        self.github = Github(self.config["token"])
        self.repo: Repository = self.github.get_repo(repo)

    def _validate_config(self) -> None:
        """Validate GitHub configuration."""
        if not self.config.get("token"):
            raise ValueError("GitHub token is required")

        if not self.config.get("repo"):
            raise ValueError("Repository is required")

        if "/" not in self.config["repo"]:
            raise ValueError("Repository must be in format 'owner/repo'")

    def _ensure_labels_exist(self, labels: list[str]):
        """Ensure labels exist in the repository, create them if needed."""
        existing_labels = {label.name for label in self.repo.get_labels()}

        for label in labels:
            if label not in existing_labels:
                try:
                    # Create label with default color
                    self.repo.create_label(
                        name=label,
                        color="0366d6",  # Default blue color
                        description=f"Auto-created label for {label}"
                    )
                except Exception:
                    # If label creation fails, skip this label
                    pass

    def _prepare_labels(
        self,
        labels: list[str] | None,
        priority: str | None,
    ) -> list[str]:
        """Build label list, filtering old priority labels and adding defaults."""
        issue_labels = []
        if labels:
            for label in labels:
                if not label.startswith("priority: "):
                    issue_labels.append(label)
        if priority:
            priority_label = f"priority-{priority}"
            if priority_label not in issue_labels:
                issue_labels.append(priority_label)
        for default in ("planfile", "managed"):
            if default not in issue_labels:
                issue_labels.append(default)
        self._ensure_labels_exist(issue_labels)
        return issue_labels

    def _build_metadata_body(self, body: str, metadata: dict[str, Any] | None) -> str:
        """Append strategy metadata section to body."""
        if not metadata:
            return body
        metadata_section = "\n\n---\n\n**Strategy Metadata:**\n"
        for key, value in metadata.items():
            if key != "model_hints":
                metadata_section += f"- {key}: {value}\n"
        if "model_hints" in metadata:
            metadata_section += "\n**Model Hints:**\n"
            for phase, tier in metadata["model_hints"].items():
                if tier:
                    metadata_section += f"- {phase}: {tier}\n"
        return body + metadata_section

    def _create_ticket(
        self,
        name: str,
        body: str,
        labels: list[str] | None = None,
        priority: str | None = None,
        backend_tag: str = "github",
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TicketRef:
        """Create a new GitHub issue."""
        issue_labels = self._prepare_labels(labels, priority)
        body = self._build_metadata_body(body, metadata)

        create_kwargs = {
            "title": name,
            "body": body,
            "labels": issue_labels,
        }
        if assignee:
            create_kwargs["assignee"] = assignee

        issue: Issue = self.repo.create_issue(**create_kwargs)

        return self.build_ticket_ref(
            id=str(issue.number),
            url=issue.html_url,
            key=f"{self.repo.full_name}#{issue.number}",
            status=issue.state,
            metadata=metadata,
        )

    def _update_labels(
        self,
        issue: Issue,
        labels: list[str] | None,
        priority: str | None,
    ) -> None:
        """Update issue labels, replacing priority labels."""
        current_labels = [label.name for label in issue.labels]
        current_labels = [l for l in current_labels if not l.startswith("priority: ")]
        new_labels = labels or []
        if priority:
            new_labels.append(f"priority: {priority}")
        issue.set_labels(*current_labels, *new_labels)

    def _update_issue_state(self, issue: Issue, status: str) -> None:
        """Update issue open/closed state."""
        status_lower = status.lower()
        if status_lower == "closed":
            issue.edit(state="closed")
        elif status_lower == "open":
            issue.edit(state="open")

    def _update_ticket(
        self,
        ticket_id: str,
        name: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list[str] | None = None,
        priority: str | None = None,
        backend_tag: str = "github",
        assignee: str | None = None,
    ) -> None:
        """Update an existing GitHub issue."""
        issue = self.repo.get_issue(int(ticket_id))

        if name:
            issue.edit(title=name)
        if body:
            issue.edit(body=body)
        if labels is not None or priority:
            self._update_labels(issue, labels, priority)
        if status:
            self._update_issue_state(issue, status)
        if assignee:
            issue.edit(assignee=assignee)

    def _get_ticket(self, ticket_id: str) -> TicketState:
        """Get GitHub issue status."""
        issue = self.repo.get_issue(int(ticket_id))

        return self._issue_to_ticket_status(issue)

    def _issue_to_ticket_status(self, issue: Issue) -> TicketState:
        """Convert a GitHub issue object into a TicketState."""
        return self.build_ticket_state(
            id=str(issue.number),
            status=issue.state,
            assignee=issue.assignee.login if issue.assignee else None,
            labels=[label.name for label in issue.labels],
            updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
        )

    def _list_tickets(
        self,
        labels: list[str] | None = None,
        status: str | None = None,
        backend_tag: str = "github",
        assignee: str | None = None,
        limit: int | None = None,
    ) -> list[TicketState]:
        """List GitHub issues with filters."""
        state = "all" if not status else status.lower()

        # Build kwargs - only include optional params if provided
        kwargs = {"state": state}
        if labels:
            kwargs["labels"] = labels
        if assignee:
            kwargs["assignee"] = assignee

        issues = self.repo.get_issues(**kwargs)

        tickets = []
        # GitHub listing path
        for issue in issues:
            if limit and len(tickets) >= limit:
                break
            tickets.append(self._issue_to_ticket_status(issue))

        return tickets

    def _search_tickets(self, query: str) -> list[TicketState]:
        """Search GitHub issues."""
        issues = self.repo.get_issues(state="all")

        tickets = []
        # GitHub search path
        for issue in issues:
            if query.lower() in issue.title.lower() or query.lower() in issue.body.lower():
                tickets.append(self._issue_to_ticket_status(issue))

        return tickets
