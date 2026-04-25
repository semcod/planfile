from datetime import datetime
from typing import Any

from planfile.sync.base import BasePMBackend, TicketRef, TicketState


class MockBackend(BasePMBackend):
    """Mock backend for examples and testing that doesn't require any credentials."""

    def __init__(self):
        """Initialize mock backend with minimal config."""
        config = {"mock": True}
        super().__init__(config)
        self.tickets = {}
        self.ticket_counter = 1

    def _create_ticket(
        self,
        name: str,
        body: str,
        labels: list | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        backend_tag: str = "mock",
    ) -> TicketRef:
        """Create a mock ticket."""
        ticket_id = str(self.ticket_counter)
        self.ticket_counter += 1

        # Store ticket data
        self.tickets[ticket_id] = {
            "id": ticket_id,
            "name": name,
            "description": body,
            "labels": labels or [],
            "priority": priority or "medium",
            "assignee": assignee,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        print(f"  [MOCK] Created ticket #{ticket_id}: {name}")

        return self.build_ticket_ref(
            id=ticket_id,
            url=f"https://mock.example.com/tickets/{ticket_id}",
            key=f"MOCK-{ticket_id}",
            status="open",
            metadata={"mock": True, "created": True}
        )

    def _update_ticket(
        self,
        ticket_id: str,
        name: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        *,
        backend_tag: str = "mock",
    ) -> None:
        """Update a mock ticket."""
        if ticket_id not in self.tickets:
            print(f"  [MOCK] Ticket #{ticket_id} not found")
            return

        ticket = self.tickets[ticket_id]
        if name:
            ticket["name"] = name
        if body:
            ticket["description"] = body
        if status:
            ticket["status"] = status
        if labels:
            ticket["labels"] = labels
        if priority:
            ticket["priority"] = priority
        if assignee:
            ticket["assignee"] = assignee

        ticket["updated_at"] = datetime.now().isoformat()

        print(f"  [MOCK] Updated ticket #{ticket_id}: {ticket.get('name', 'No title')}")

    def _get_ticket(self, ticket_id: str) -> TicketState:
        """Get mock ticket status."""
        if ticket_id not in self.tickets:
            raise ValueError(f"Ticket #{ticket_id} not found")

        ticket = self.tickets[ticket_id]
        return self.build_ticket_state(
            id=ticket["id"],
            key=f"MOCK-{ticket['id']}",
            status=ticket["status"],
            assignee=ticket.get("assignee"),
            labels=ticket.get("labels", []),
            updated_at=ticket.get("updated_at")
        )

    def _list_tickets(
        self,
        labels: list | None = None,
        status: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
        *,
        backend_tag: str = "mock",
    ) -> list[TicketState]:
        """List mock tickets."""
        tickets = []

        for ticket_data in self.tickets.values():
            # Apply filters
            if labels and not any(label in ticket_data.get("labels", []) for label in labels):
                continue
            if status and ticket_data.get("status") != status:
                continue
            if assignee and ticket_data.get("assignee") != assignee:
                continue

            tickets.append(self.build_ticket_state(
                id=ticket_data["id"],
                key=f"MOCK-{ticket_data['id']}",
                status=ticket_data["status"],
                assignee=ticket_data.get("assignee"),
                labels=ticket_data.get("labels", []),
                updated_at=ticket_data.get("updated_at")
            ))

            if limit and len(tickets) >= limit:
                break

        print(f"  [MOCK] Listed {len(tickets)} tickets")
        return tickets

    def _search_tickets(self, query: str) -> list[TicketState]:
        """Search mock tickets."""
        tickets = []
        query_lower = query.lower()

        for ticket_data in self.tickets.values():
            if (query_lower in ticket_data.get("name", "").lower() or
                query_lower in ticket_data.get("title", "").lower() or
                query_lower in ticket_data["description"].lower()):
                tickets.append(self.build_ticket_state(
                    id=ticket_data["id"],
                    key=f"MOCK-{ticket_data['id']}",
                    status=ticket_data["status"],
                    assignee=ticket_data.get("assignee"),
                    labels=ticket_data.get("labels", []),
                    updated_at=ticket_data.get("updated_at")
                ))

        print(f"  [MOCK] Found {len(tickets)} tickets matching '{query}'")
        return tickets
