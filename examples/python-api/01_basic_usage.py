#!/usr/bin/env python3
"""
Basic usage of planfile as a Python library.

This example shows how to:
1. Initialize Planfile with auto-discovery
2. Create and manage tickets programmatically
3. Use the quick_ticket helper
"""

from pathlib import Path
from planfile import Planfile, quick_ticket, Ticket


def example_1_basic_initialization():
    """Initialize planfile with auto-discovery."""
    print("=== Example 1: Basic Initialization ===\n")
    
    # Auto-discover .planfile/ in current or parent directories
    pf = Planfile.auto_discover(".")
    print(f"✓ Planfile initialized at: {pf.store.project_path}")
    print(f"  Store path: {pf.store.store_path}")
    print()


def example_2_create_ticket():
    """Create a ticket programmatically."""
    print("=== Example 2: Creating a Ticket ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Create a simple ticket
    ticket = pf.create_ticket(
        title="Fix authentication bug",
        description="Users cannot login with OAuth provider",
        priority="high",
        status="open",
        labels=["bug", "backend", "security"],
        sprint="current"
    )
    
    print(f"✓ Created ticket: {ticket.id}")
    print(f"  Title: {ticket.title}")
    print(f"  Priority: {ticket.priority}")
    print(f"  Status: {ticket.status}")
    print(f"  Sprint: {ticket.sprint}")
    print()


def example_3_quick_ticket():
    """Use quick_ticket helper for one-off ticket creation."""
    print("=== Example 3: Quick Ticket Helper ===\n")
    
    # One-liner for tools and scripts
    ticket = quick_ticket(
        title="Production alert: High memory usage on prod-01",
        tool="monitoring-system",
        priority="critical",
        context={
            "server": "prod-01",
            "metric": "memory",
            "threshold": "90%",
            "duration": "5m"
        }
    )
    
    print(f"✓ Created quick ticket: {ticket.id}")
    print(f"  Source tool: {ticket.source.tool}")
    print(f"  Context: {ticket.source.context}")
    print()


def example_4_list_tickets():
    """List and filter tickets."""
    print("=== Example 4: Listing Tickets ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # List all tickets in current sprint
    tickets = pf.list_tickets(sprint="current")
    print(f"Found {len(tickets)} tickets in current sprint:\n")
    
    for t in tickets[:5]:  # Show first 5
        print(f"  {t.id}: {t.title} [{t.status}]")
    
    if len(tickets) > 5:
        print(f"  ... and {len(tickets) - 5} more")
    
    # Filter by status
    open_tickets = pf.list_tickets(status="open")
    print(f"\n  Open tickets: {len(open_tickets)}")
    print()


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Planfile Python Library - Basic Usage Examples")
    print("="*60 + "\n")
    
    example_1_basic_initialization()
    example_2_create_ticket()
    example_3_quick_ticket()
    example_4_list_tickets()
    
    print("="*60)
    print("All examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
