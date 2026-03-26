from typing import Dict, Any, Optional
import requests
import json

from planfile.integrations.base import BasePMBackend, TicketRef, TicketStatus


class GenericBackend(BasePMBackend):
    """Generic HTTP API backend for PM systems."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Initialize generic backend.
        
        Args:
            base_url: Base URL for the API
            api_key: API key for authentication
            headers: Additional headers to send with requests
        """
        config = {
            "base_url": base_url.rstrip("/"),
            "api_key": api_key,
            "headers": headers or {},
            **kwargs
        }
        super().__init__(config)
        
        self.session = requests.Session()
        
        # Set up authentication
        if self.config["api_key"]:
            self.session.headers.update({"Authorization": f"Bearer {self.config['api_key']}"})
        
        # Set up additional headers
        if self.config["headers"]:
            self.session.headers.update(self.config["headers"])
        
        # Default to JSON content type
        self.session.headers.update({"Content-Type": "application/json"})
    
    def _validate_config(self) -> None:
        """Validate generic backend configuration."""
        if not self.config.get("base_url"):
            raise ValueError("Base URL is required")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to the API."""
        url = f"{self.config['base_url']}/{endpoint.lstrip('/')}"
        
        response = self.session.request(
            method=method,
            url=url,
            json=data,
            params=params
        )
        
        if not response.ok:
            raise RuntimeError(f"API request failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def create_ticket(
        self,
        title: str,
        body: str,
        labels: Optional[list] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TicketRef:
        """Create a new ticket via generic API."""
        data = {
            "title": title,
            "description": body,
            "labels": labels or [],
            "priority": priority,
            "assignee": assignee,
            "metadata": self.prepare_metadata(metadata)
        }
        
        # Add strategy metadata
        if metadata:
            data["strategy_metadata"] = metadata
        
        response = self._make_request("POST", "/tickets", data=data)
        
        return TicketRef(
            id=str(response.get("id")),
            url=response.get("url"),
            key=response.get("key"),
            status=response.get("status"),
            metadata=response.get("metadata", {})
        )
    
    def update_ticket(
        self,
        ticket_id: str,
        title: Optional[str] = None,
        body: Optional[str] = None,
        status: Optional[str] = None,
        labels: Optional[list] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> None:
        """Update a ticket via generic API."""
        data = {}
        
        if title:
            data["title"] = title
        if body:
            data["description"] = body
        if status:
            data["status"] = status
        if labels:
            data["labels"] = labels
        if priority:
            data["priority"] = priority
        if assignee:
            data["assignee"] = assignee
        
        if data:
            self._make_request("PUT", f"/tickets/{ticket_id}", data=data)
    
    def get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get ticket status via generic API."""
        response = self._make_request("GET", f"/tickets/{ticket_id}")
        
        return TicketStatus(
            id=str(response.get("id")),
            status=response.get("status"),
            assignee=response.get("assignee"),
            labels=response.get("labels", []),
            updated_at=response.get("updated_at")
        )
    
    def list_tickets(
        self,
        labels: Optional[list] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[TicketStatus]:
        """List tickets via generic API."""
        params = {}
        
        if labels:
            params["labels"] = ",".join(labels)
        if status:
            params["status"] = status
        if assignee:
            params["assignee"] = assignee
        if limit:
            params["limit"] = limit
        
        response = self._make_request("GET", "/tickets", params=params)
        
        tickets = []
        for ticket_data in response.get("tickets", []):
            tickets.append(TicketStatus(
                id=str(ticket_data.get("id")),
                status=ticket_data.get("status"),
                assignee=ticket_data.get("assignee"),
                labels=ticket_data.get("labels", []),
                updated_at=ticket_data.get("updated_at")
            ))
        
        return tickets
    
    def search_tickets(self, query: str) -> list[TicketStatus]:
        """Search tickets via generic API."""
        params = {"q": query}
        
        response = self._make_request("GET", "/tickets/search", params=params)
        
        tickets = []
        for ticket_data in response.get("tickets", []):
            tickets.append(TicketStatus(
                id=str(ticket_data.get("id")),
                status=ticket_data.get("status"),
                assignee=ticket_data.get("assignee"),
                labels=ticket_data.get("labels", []),
                updated_at=ticket_data.get("updated_at")
            ))
        
        return tickets
