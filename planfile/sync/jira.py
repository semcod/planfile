import os
from typing import Optional, List, Dict, Any
try:
    from jira import JIRA
    from jira.exceptions import JIRAError
except ImportError:
    JIRA = None
    JIRAError = None  # pip install jira

from planfile.sync.base import BasePMBackend, TicketRef, TicketStatus


class JiraBackend(BasePMBackend):
    """Jira integration backend."""
    
    def __init__(
        self,
        base_url: str,
        email: Optional[str] = None,
        token: Optional[str] = None,
        project: Optional[str] = None,
        **kwargs
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
            **kwargs
        }
        super().__init__(config)
        
        self.jira = JIRA(
            server=self.config["base_url"],
            basic_auth=(self.config["email"], self.config["token"])
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
    
    def _map_priority_to_jira(self, priority: Optional[str]) -> str:
        """Map generic priority to Jira priority."""
        if not priority:
            return "Medium"
        
        priority_map = self.config.get("priority_map", {
            "lowest": "Lowest",
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "highest": "Highest",
        })
        
        return priority_map.get(priority.lower(), "Medium")
    
    def _map_task_type_to_jira(self, task_type: str) -> str:
        """Map task type to Jira issue type."""
        type_map = self.config.get("type_map", {
            "feature": "Story",
            "tech_debt": "Task",
            "bug": "Bug",
            "chore": "Task",
            "documentation": "Task",
        })
        
        return type_map.get(task_type.lower(), "Task")
    
    def create_ticket(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TicketRef:
        """Create a new Jira issue."""
        issue_dict = {
            "project": {"key": self.config["project"]},
            "summary": title,
            "description": body,
            "issuetype": {"name": "Task"},  # Default type
        }
        
        # Add priority
        if priority:
            issue_dict["priority"] = {"name": self._map_priority_to_jira(priority)}
        
        # Add labels
        if labels:
            issue_dict["labels"] = labels
        
        # Add strategy metadata to description
        if metadata:
            metadata_section = "\n\n---\n\n*Strategy Metadata:*\n"
            for key, value in metadata.items():
                if key != "model_hints" and key != "type":
                    metadata_section += f"* {key}: {value}\n"
            
            if "type" in metadata:
                issue_dict["issuetype"] = {"name": self._map_task_type_to_jira(metadata["type"])}
            
            if "model_hints" in metadata:
                metadata_section += "\n*Model Hints:*\n"
                for phase, tier in metadata["model_hints"].items():
                    if tier:
                        metadata_section += f"* {phase}: {tier}\n"
            
            issue_dict["description"] += metadata_section
        
        # Create issue
        try:
            issue = self.jira.create_issue(fields=issue_dict)
            
            # Assign if specified
            if assignee:
                self.jira.assign_issue(issue, assignee)
            
            return TicketRef(
                id=issue.id,
                url=f"{self.config['base_url']}/browse/{issue.key}",
                key=issue.key,
                status=issue.fields.status.name,
                metadata=self.prepare_metadata(metadata)
            )
        except JIRAError as e:
            raise RuntimeError(f"Failed to create Jira issue: {e}")
    
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
        """Update an existing Jira issue."""
        try:
            issue = self.jira.issue(ticket_id)
            
            # Update fields
            fields = {}
            
            if title:
                fields["summary"] = title
            
            if body:
                fields["description"] = body
            
            if priority:
                fields["priority"] = {"name": self._map_priority_to_jira(priority)}
            
            if labels is not None:
                fields["labels"] = labels
            
            if fields:
                issue.update(fields=fields)
            
            # Update status (transition)
            if status:
                transitions = self.jira.transitions(issue)
                for transition in transitions:
                    if transition["name"].lower() == status.lower():
                        self.jira.transition_issue(issue, transition["id"])
                        break
            
            # Update assignee
            if assignee:
                self.jira.assign_issue(issue, assignee)
                
        except JIRAError as e:
            raise RuntimeError(f"Failed to update Jira issue {ticket_id}: {e}")
    
    def get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get Jira issue status."""
        try:
            issue = self.jira.issue(ticket_id)
            
            return TicketStatus(
                id=issue.id,
                key=issue.key,
                status=issue.fields.status.name,
                assignee=issue.fields.assignee.displayName if issue.fields.assignee else None,
                labels=issue.fields.labels or [],
                updated_at=issue.fields.updated.isoformat() if issue.fields.updated else None
            )
        except JIRAError as e:
            raise RuntimeError(f"Failed to get Jira issue {ticket_id}: {e}")
    
    def list_tickets(
        self,
        labels: Optional[List[str]] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TicketStatus]:
        """List Jira issues with filters."""
        jql = f'project = {self.config["project"]}'
        
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
                fields=["summary", "status", "assignee", "labels", "updated"]
            )
            
            tickets = []
            for issue in issues:
                tickets.append(TicketStatus(
                    id=issue.id,
                    key=issue.key,
                    status=issue.fields.status.name,
                    assignee=issue.fields.assignee.displayName if issue.fields.assignee else None,
                    labels=issue.fields.labels or [],
                    updated_at=issue.fields.updated.isoformat() if issue.fields.updated else None
                ))
            
            return tickets
        except JIRAError as e:
            raise RuntimeError(f"Failed to list Jira issues: {e}")
    
    def search_tickets(self, query: str) -> List[TicketStatus]:
        """Search Jira issues."""
        jql = f'project = {self.config["project"]} AND text ~ "{query}" ORDER BY updated DESC'
        
        try:
            issues = self.jira.search_issues(
                jql,
                maxResults=50,
                fields=["summary", "status", "assignee", "labels", "updated"]
            )
            
            tickets = []
            for issue in issues:
                tickets.append(TicketStatus(
                    id=issue.id,
                    key=issue.key,
                    status=issue.fields.status.name,
                    assignee=issue.fields.assignee.displayName if issue.fields.assignee else None,
                    labels=issue.fields.labels or [],
                    updated_at=issue.fields.updated.isoformat() if issue.fields.updated else None
                ))
            
            return tickets
        except JIRAError as e:
            raise RuntimeError(f"Failed to search Jira issues: {e}")
