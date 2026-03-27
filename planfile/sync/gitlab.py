import os
from typing import Optional, List, Dict, Any
try:
    import gitlab
    from gitlab.exceptions import GitlabError
except ImportError:
    gitlab = None
    GitlabError = None  # pip install python-gitlab

from planfile.sync.base import BasePMBackend, TicketRef, TicketStatus


class GitLabBackend(BasePMBackend):
    """GitLab Issues integration backend."""
    
    def __init__(
        self,
        url: str = "https://gitlab.com",
        token: Optional[str] = None,
        project_id: Optional[int] = None,
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
    
    def create_ticket(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TicketRef:
        """Create a new GitLab issue."""
        # Prepare labels
        issue_labels = labels or []
        
        # Add priority as label if specified
        if priority:
            priority_label = f"priority::{priority}"
            issue_labels.append(priority_label)
        
        # Add strategy metadata to body
        if metadata:
            metadata_section = "\n\n---\n\n### Strategy Metadata\n\n"
            for key, value in metadata.items():
                if key != "model_hints":
                    metadata_section += f"- **{key}**: {value}\n"
            
            if "model_hints" in metadata:
                metadata_section += "\n### Model Hints\n\n"
                for phase, tier in metadata["model_hints"].items():
                    if tier:
                        metadata_section += f"- **{phase}**: {tier}\n"
            
            body += metadata_section
        
        # Create issue
        try:
            issue = self.project.issues.create({
                "title": title,
                "description": body,
                "labels": issue_labels,
            })
            
            # Assign if specified
            if assignee:
                # Get user by username
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
        """Update an existing GitLab issue."""
        try:
            issue = self.project.issues.get(ticket_id)
            
            # Update title
            if title:
                issue.title = title
            
            # Update description
            if body:
                issue.description = body
            
            # Update labels
            if labels is not None or priority:
                current_labels = issue.labels
                
                # Remove existing priority labels
                current_labels = [l for l in current_labels if not l.startswith("priority::")]
                
                # Add new labels
                new_labels = labels or []
                if priority:
                    new_labels.append(f"priority::{priority}")
                
                issue.labels = current_labels + new_labels
            
            # Update state (open/close)
            if status:
                if status.lower() == "closed":
                    issue.state_event = "close"
                elif status.lower() == "open":
                    issue.state_event = "reopen"
            
            # Update assignee
            if assignee:
                users = self.gl.users.list(username=assignee)
                if users:
                    issue.assignee_id = users[0].id
            
            issue.save()
            
        except GitlabError as e:
            raise RuntimeError(f"Failed to update GitLab issue {ticket_id}: {e}")
    
    def get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get GitLab issue status."""
        try:
            issue = self.project.issues.get(ticket_id)
            
            return self.build_ticket_status(
                id=str(issue.iid),
                status=issue.state,
                assignee=issue.assignee["username"] if issue.assignee else None,
                labels=issue.labels or [],
                updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
            )
        except GitlabError as e:
            raise RuntimeError(f"Failed to get GitLab issue {ticket_id}: {e}")
    
    def list_tickets(
        self,
        labels: Optional[List[str]] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TicketStatus]:
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
                tickets.append(self.build_ticket_status(
                    id=str(issue.iid),
                    status=issue.state,
                    assignee=issue.assignee["username"] if issue.assignee else None,
                    labels=issue.labels or [],
                    updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
                ))
            
            return tickets
        except GitlabError as e:
            raise RuntimeError(f"Failed to list GitLab issues: {e}")
    
    def search_tickets(self, query: str) -> List[TicketStatus]:
        """Search GitLab issues."""
        try:
            issues = self.project.issues.list(search=query, state="all", per_page=50)
            
            tickets = []
            for issue in issues:
                tickets.append(self.build_ticket_status(
                    id=str(issue.iid),
                    status=issue.state,
                    assignee=issue.assignee["username"] if issue.assignee else None,
                    labels=issue.labels or [],
                    updated_at=issue.updated_at.isoformat() if issue.updated_at else None,
                ))
            
            return tickets
        except GitlabError as e:
            raise RuntimeError(f"Failed to search GitLab issues: {e}")
