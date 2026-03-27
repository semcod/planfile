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
    status: str
    assignee: Optional[str] = None
    labels: List[str] = []
    updated_at: Optional[str] = None


class PMBackend(Protocol):
    """Protocol for PM system backends."""
    
    @abstractmethod
    def create_ticket(self, **kwargs) -> TicketRef:
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
        status: str,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
        updated_at: Optional[str] = None,
        **extra: Any,
    ) -> TicketStatus:
        """Build a TicketStatus with consistent defaults."""
        return TicketStatus(
            id=id,
            status=status,
            assignee=assignee,
            labels=labels or [],
            updated_at=updated_at,
            **extra,
        )
