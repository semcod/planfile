import os
from typing import Optional, List, Dict, Any
from github import Github
from github.Issue import Issue
from github.Repository import Repository

from .base import BasePMBackend, TicketRef, TicketStatus


class GitHubBackend(BasePMBackend):
    """GitHub Issues integration backend."""
    
    def __init__(self, repo: str, token: Optional[str] = None, **kwargs):
        """
        Initialize GitHub backend.
        
        Args:
            repo: Repository in format "owner/repo"
            token: GitHub token (defaults to GITHUB_TOKEN env var)
        """
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
    
    def create_ticket(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TicketRef:
        """Create a new GitHub issue."""
        # Prepare labels
        issue_labels = labels or []
        
        # Add priority as label if specified
        if priority:
            priority_label = f"priority: {priority}"
            issue_labels.append(priority_label)
        
        # Add strategy metadata to body
        if metadata:
            metadata_section = "\n\n---\n\n**Strategy Metadata:**\n"
            for key, value in metadata.items():
                if key != "model_hints":
                    metadata_section += f"- {key}: {value}\n"
            if "model_hints" in metadata:
                metadata_section += "\n**Model Hints:**\n"
                for phase, tier in metadata["model_hints"].items():
                    if tier:
                        metadata_section += f"- {phase}: {tier}\n"
            body += metadata_section
        
        # Create issue
        issue: Issue = self.repo.create_issue(
            title=title,
            body=body,
            labels=issue_labels,
            assignee=assignee
        )
        
        return TicketRef(
            id=str(issue.number),
            url=issue.html_url,
            key=f"{self.repo.full_name}#{issue.number}",
            status=issue.state,
            metadata=self.prepare_metadata(metadata)
        )
    
    def update_ticket(
        self,
        ticket_id: str,
        title: Optional[str] = None,
        body: Optional[str] = None,
        status: Optional[str] = None,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> None:
        """Update an existing GitHub issue."""
        issue = self.repo.get_issue(int(ticket_id))
        
        # Update title
        if title:
            issue.edit(title=title)
        
        # Update body
        if body:
            issue.edit(body=body)
        
        # Update labels
        if labels is not None or priority:
            current_labels = [label.name for label in issue.labels]
            
            # Remove existing priority labels
            current_labels = [l for l in current_labels if not l.startswith("priority: ")]
            
            # Add new labels
            new_labels = labels or []
            if priority:
                new_labels.append(f"priority: {priority}")
            
            issue.set_labels(*current_labels, *new_labels)
        
        # Update state (open/close)
        if status:
            if status.lower() == "closed":
                issue.edit(state="closed")
            elif status.lower() == "open":
                issue.edit(state="open")
        
        # Update assignee
        if assignee:
            issue.edit(assignee=assignee)
    
    def get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get GitHub issue status."""
        issue = self.repo.get_issue(int(ticket_id))
        
        return TicketStatus(
            id=str(issue.number),
            status=issue.state,
            assignee=issue.assignee.login if issue.assignee else None,
            labels=[label.name for label in issue.labels],
            updated_at=issue.updated_at.isoformat() if issue.updated_at else None
        )
    
    def list_tickets(
        self,
        labels: Optional[List[str]] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TicketStatus]:
        """List GitHub issues with filters."""
        state = "all" if not status else status.lower()
        
        issues = self.repo.get_issues(
            state=state,
            labels=labels,
            assignee=assignee
        )
        
        tickets = []
        for issue in issues:
            if limit and len(tickets) >= limit:
                break
            
            tickets.append(TicketStatus(
                id=str(issue.number),
                status=issue.state,
                assignee=issue.assignee.login if issue.assignee else None,
                labels=[label.name for label in issue.labels],
                updated_at=issue.updated_at.isoformat() if issue.updated_at else None
            ))
        
        return tickets
    
    def search_tickets(self, query: str) -> List[TicketStatus]:
        """Search GitHub issues."""
        issues = self.repo.get_issues(state="all")
        
        tickets = []
        for issue in issues:
            if query.lower() in issue.title.lower() or query.lower() in issue.body.lower():
                tickets.append(TicketStatus(
                    id=str(issue.number),
                    status=issue.state,
                    assignee=issue.assignee.login if issue.assignee else None,
                    labels=[label.name for label in issue.labels],
                    updated_at=issue.updated_at.isoformat() if issue.updated_at else None
                ))
        
        return tickets
