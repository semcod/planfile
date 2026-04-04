#!/usr/bin/env python3
"""
Python client for planfile REST API.

Shows how to use the API with httpx (modern) or requests.
"""

import json
import sys
from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    try:
        import requests
        HAS_REQUESTS = True
    except ImportError:
        print("Error: Install httpx or requests: pip install httpx")
        sys.exit(1)


class PlanfileClient:
    """Python client for planfile REST API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        
        if HAS_HTTPX:
            self.client = httpx.Client(base_url=base_url)
        else:
            self.client = requests.Session()
            self.client.headers.update({"Accept": "application/json"})
    
    def _request(self, method: str, path: str, **kwargs):
        """Make HTTP request."""
        url = f"{self.base_url}{path}"
        
        if HAS_HTTPX:
            response = self.client.request(method, path, **kwargs)
        else:
            response = self.client.request(method, url, **kwargs)
        
        response.raise_for_status()
        return response.json() if response.content else None
    
    def health(self) -> dict:
        """Check server health."""
        return self._request("GET", "/health")
    
    def list_tickets(
        self,
        sprint: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None
    ) -> list:
        """List tickets with optional filters."""
        params = {}
        if sprint:
            params["sprint"] = sprint
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        
        return self._request("GET", "/tickets", params=params)
    
    def create_ticket(
        self,
        title: str,
        description: str = "",
        priority: str = "normal",
        sprint: str = "current",
        labels: Optional[list] = None
    ) -> dict:
        """Create a new ticket."""
        data = {
            "title": title,
            "description": description,
            "priority": priority,
            "sprint": sprint,
            "labels": labels or []
        }
        return self._request("POST", "/tickets", json=data)
    
    def get_ticket(self, ticket_id: str) -> dict:
        """Get single ticket by ID."""
        return self._request("GET", f"/tickets/{ticket_id}")
    
    def update_ticket(self, ticket_id: str, **updates) -> dict:
        """Update ticket properties."""
        return self._request("PATCH", f"/tickets/{ticket_id}", json=updates)
    
    def move_ticket(self, ticket_id: str, to_sprint: str) -> dict:
        """Move ticket to different sprint."""
        return self._request(
            "POST",
            f"/tickets/{ticket_id}/move",
            params={"to_sprint": to_sprint}
        )
    
    def delete_ticket(self, ticket_id: str) -> None:
        """Delete ticket."""
        self._request("DELETE", f"/tickets/{ticket_id}")


def example_basic_operations():
    """Basic CRUD operations."""
    print("=== Python Client: Basic Operations ===\n")
    
    client = PlanfileClient()
    
    # Health check
    health = client.health()
    print(f"✓ Server status: {health}")
    
    # Create ticket
    ticket = client.create_ticket(
        title="Python API Test: Database optimization",
        description="Query performance needs improvement",
        priority="high",
        labels=["performance", "database"]
    )
    print(f"✓ Created: {ticket['id']}")
    
    # Get ticket
    fetched = client.get_ticket(ticket['id'])
    print(f"✓ Fetched: {fetched['title']}")
    
    # Update
    updated = client.update_ticket(
        ticket['id'],
        status="in_progress",
        assignee="developer"
    )
    print(f"✓ Updated: status={updated['status']}, assignee={updated.get('assignee')}")
    
    return ticket['id']


def example_bulk_operations():
    """Bulk create and list."""
    print("\n=== Python Client: Bulk Operations ===\n")
    
    client = PlanfileClient()
    
    # Bulk create
    tickets = []
    for i in range(3):
        ticket = client.create_ticket(
            title=f"Bulk Ticket {i+1}: API Test",
            priority="medium",
            sprint="current"
        )
        tickets.append(ticket['id'])
    
    print(f"✓ Created {len(tickets)} tickets")
    
    # List all
    all_tickets = client.list_tickets()
    print(f"✓ Total tickets: {len(all_tickets)}")
    
    # Filter by sprint
    current = client.list_tickets(sprint="current")
    print(f"✓ Current sprint: {len(current)}")
    
    return tickets


def example_workflow(ticket_id: str):
    """Complete ticket workflow."""
    print("\n=== Python Client: Workflow Example ===\n")
    
    client = PlanfileClient()
    
    # 1. New ticket
    ticket = client.get_ticket(ticket_id)
    print(f"1. New ticket: {ticket['status']}")
    
    # 2. Start work
    client.update_ticket(ticket_id, status="in_progress")
    print("2. Started work")
    
    # 3. Move to next sprint
    client.move_ticket(ticket_id, to_sprint="sprint-2")
    print("3. Moved to sprint-2")
    
    # 4. Complete
    client.update_ticket(ticket_id, status="done")
    print("4. Marked as done")
    
    # Verify
    final = client.get_ticket(ticket_id)
    print(f"\nFinal state: {final['status']} in {final.get('sprint', 'unknown')}")


def example_error_handling():
    """Handle API errors gracefully."""
    print("\n=== Python Client: Error Handling ===\n")
    
    client = PlanfileClient()
    
    try:
        # Try to get non-existent ticket
        client.get_ticket("NONEXISTENT-99999")
    except Exception as e:
        print(f"✓ Handled 404: {type(e).__name__}")
    
    try:
        # Try invalid data
        client.create_ticket(title="")  # Empty title might fail
    except Exception as e:
        print(f"✓ Handled validation error: {type(e).__name__}")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Planfile REST API - Python Client")
    print("="*60 + "\n")
    
    lib = "httpx" if HAS_HTTPX else "requests"
    print(f"Using: {lib}\n")
    
    try:
        ticket_id = example_basic_operations()
        bulk_ids = example_bulk_operations()
        example_workflow(ticket_id)
        example_error_handling()
        
        print("\n" + "="*60)
        print("All Python client examples completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure the server is running:")
        print("  ./01_start_server.sh")
        sys.exit(1)


if __name__ == "__main__":
    main()
