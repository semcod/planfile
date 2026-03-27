from abc import ABC, abstractmethod
from typing import Protocol, Optional, Dict, Any, List
from pydantic import BaseModel


class TicketRef(BaseModel):
    """Reference to a created/updated ticket."""
    id: str
    url: Optional[str] = None
    key: Optional[str] = None  # For systems like Jira that have ticket keys
    status: Optional[str] = None
    metadata: Dict[str, Any] = {}


class TicketStatus(BaseModel):
    """Status of a ticket."""
    id: str
    key: Optional[str] = None
    status: str
    assignee: Optional[str] = None
    labels: List[str] = []
    updated_at: Optional[str] = None


class PMBackend(Protocol):
    """Protocol for PM system backends."""
    
    @abstractmethod
    def create_ticket(self, ticket: Dict[str, Any], **kwargs) -> TicketRef:
        """Create a new ticket."""
        ...
    
    @abstractmethod
    def update_ticket(self, **kwargs) -> None:
        """Update an existing ticket."""
        ...
    
    @abstractmethod
    def get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get ticket status."""
        ...
    
    @abstractmethod
    def list_tickets(self, **kwargs) -> List[TicketStatus]:
        """List tickets with filters."""
        ...
    
    @abstractmethod
    def search_tickets(self, query: str) -> List[TicketStatus]:
        """Search tickets by query."""
        ...


class BasePMBackend(ABC):
    """Base class for PM backends with common functionality."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate backend configuration."""
        pass
    
    def map_priority(self, priority: Optional[str]) -> str:
        """Map generic priority to backend-specific priority."""
        if not priority:
            return "medium"
        
        priority_map = self.config.get("priority_map", {
            "lowest": "lowest",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "highest": "highest",
        })
        
        return priority_map.get(priority.lower(), "medium")
    
    def prepare_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare metadata for ticket creation."""
        if not metadata:
            return {}
        
        # Filter out any backend-specific metadata that shouldn't be public
        public_metadata = {k: v for k, v in metadata.items() 
                          if not k.startswith("_")}
        
        return public_metadata

    def create_ticket(self, ticket: Dict[str, Any], **kwargs) -> TicketRef:
        """Create a new ticket through the backend-specific implementation."""
        # Extract title and body from ticket object
        title = ticket.get("title", "")
        body = ticket.get("description", "") or ticket.get("body", "")
        
        return self._create_ticket(
            title=title,
            body=body,
            labels=ticket.get("labels"),
            priority=ticket.get("priority"),
            assignee=ticket.get("assignee"),
            metadata=ticket.get("metadata"),
            **kwargs
        )

    @abstractmethod
    def _create_ticket(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TicketRef:
        """Create a new ticket."""
        ...

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
        """Update an existing ticket through the backend-specific implementation."""
        return self._update_ticket(
            ticket_id=ticket_id,
            title=title,
            body=body,
            status=status,
            labels=labels,
            priority=priority,
            assignee=assignee,
        )

    @abstractmethod
    def _update_ticket(
        self,
        ticket_id: str,
        title: Optional[str] = None,
        body: Optional[str] = None,
        status: Optional[str] = None,
        labels: Optional[List[str]] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> None:
        """Update an existing ticket."""
        ...

    def get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get ticket status through the backend-specific implementation."""
        return self._get_ticket(ticket_id)

    @abstractmethod
    def _get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get ticket status."""
        ...

    def list_tickets(
        self,
        labels: Optional[List[str]] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TicketStatus]:
        """List tickets with filters through the backend-specific implementation."""
        return self._list_tickets(
            labels=labels,
            status=status,
            assignee=assignee,
            limit=limit,
        )

    @abstractmethod
    def _list_tickets(
        self,
        labels: Optional[List[str]] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TicketStatus]:
        """List tickets with filters."""
        ...

    def search_tickets(self, query: str) -> List[TicketStatus]:
        """Search tickets through the backend-specific implementation."""
        return self._search_tickets(query)

    @abstractmethod
    def _search_tickets(self, query: str) -> List[TicketStatus]:
        """Search tickets by query."""
        ...

    def build_ticket_ref(
        self,
        *,
        id: str,
        url: Optional[str] = None,
        key: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TicketRef:
        """Build a TicketRef with normalized metadata."""
        return TicketRef(
            id=id,
            url=url,
            key=key,
            status=status,
            metadata=self.prepare_metadata(metadata),
        )

    def build_ticket_status(
        self,
        *,
        id: str,
        key: Optional[str] = None,
        status: str,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
        updated_at: Optional[str] = None,
    ) -> TicketStatus:
        """Build a TicketStatus with consistent defaults."""
        return TicketStatus(
            id=id,
            key=key,
            status=status,
            assignee=assignee,
            labels=labels or [],
            updated_at=updated_at,
        )
