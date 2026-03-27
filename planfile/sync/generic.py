from typing import Any

import requests

from planfile.sync.base import BasePMBackend, TicketRef, TicketStatus


class GenericBackend(BasePMBackend):
    """Generic HTTP API backend for PM systems."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
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
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
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

    def _create_ticket(
        self,
        title: str,
        body: str,
        labels: list | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        backend_tag: str = "generic",
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

        return self.build_ticket_ref(
            id=str(response.get("id")),
            url=response.get("url"),
            key=response.get("key"),
            status=response.get("status"),
            metadata=response.get("metadata", {}),
        )

    def _update_ticket(
        self,
        ticket_id: str,
        title: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        *,
        backend_tag: str = "generic",
    ) -> None:
        """Update a ticket via generic API."""
        data = self._build_update_data(
            title=title,
            body=body,
            status=status,
            labels=labels,
            priority=priority,
            assignee=assignee
        )

        if data:
            self._make_request("PUT", f"/tickets/{ticket_id}", data=data)

    def _build_update_data(
        self,
        title: str | None = None,
        body: str | None = None,
        status: str | None = None,
        labels: list | None = None,
        priority: str | None = None,
        assignee: str | None = None,
    ) -> dict[str, Any]:
        """Build update data dictionary."""
        data = {}

        field_mapping = {
            "title": title,
            "description": body,
            "status": status,
            "labels": labels,
            "priority": priority,
            "assignee": assignee,
        }

        for key, value in field_mapping.items():
            if value is not None:
                data[key] = value

        return data

    def _get_ticket(self, ticket_id: str) -> TicketStatus:
        """Get ticket status via generic API."""
        response = self._make_request("GET", f"/tickets/{ticket_id}")

        return self._ticket_data_to_status(response)

    def _list_tickets(
        self,
        labels: list | None = None,
        status: str | None = None,
        assignee: str | None = None,
        limit: int | None = None,
        *,
        backend_tag: str = "generic",
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
            tickets.append(self._ticket_data_to_status(ticket_data))

        return tickets

    def _search_tickets(self, query: str) -> list[TicketStatus]:
        """Search tickets via generic API."""
        params = {"q": query}

        response = self._make_request("GET", "/tickets/search", params=params)

        tickets = []
        for ticket_data in response.get("tickets", []):
            tickets.append(self._ticket_data_to_status(ticket_data))

        return tickets

    def _ticket_data_to_status(self, ticket_data: dict[str, Any]) -> TicketStatus:
        """Convert a generic API ticket payload into TicketStatus."""
        return self.build_ticket_status(
            id=str(ticket_data.get("id")),
            status=ticket_data.get("status"),
            assignee=ticket_data.get("assignee"),
            labels=ticket_data.get("labels", []),
            updated_at=ticket_data.get("updated_at"),
        )
