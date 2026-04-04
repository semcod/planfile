#!/usr/bin/env python3
"""
Ticket management operations.

Shows full CRUD lifecycle:
- Create
- Read (get/list)
- Update
- Delete
"""

from planfile import Planfile, Ticket


def example_create_tickets():
    """Create multiple tickets."""
    print("=== Creating Tickets ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Create different types of tickets (using labels to categorize)
    bug = pf.create_ticket(
        title="Login button not working on mobile",
        description="Users report login button is unresponsive on iOS Safari",
        priority="high",
        labels=["bug", "mobile", "ios"],
        assignee="john.doe"
    )
    print(f"✓ Bug ticket: {bug.id}")
    
    feature = pf.create_ticket(
        title="Add dark mode support",
        description="Implement system-wide dark mode toggle",
        priority="medium",
        labels=["feature", "ui", "accessibility"]
    )
    print(f"✓ Feature ticket: {feature.id}")
    
    docs = pf.create_ticket(
        title="Update API documentation",
        description="Add examples for new endpoints",
        priority="low",
        labels=["docs", "api"]
    )
    print(f"✓ Docs ticket: {docs.id}\n")
    
    return [bug.id, feature.id, docs.id]


def example_read_tickets(ticket_ids):
    """Read/retrieve tickets."""
    print("=== Reading Tickets ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Get single ticket
    ticket = pf.get_ticket(ticket_ids[0])
    print(f"Single ticket lookup:")
    print(f"  ID: {ticket.id}")
    print(f"  Title: {ticket.title}")
    print(f"  Priority: {ticket.priority}")
    print(f"  Status: {ticket.status}")
    print()
    
    # List all tickets
    all_tickets = pf.list_tickets()
    print(f"Total tickets: {len(all_tickets)}\n")


def example_update_tickets(ticket_ids):
    """Update ticket properties."""
    print("=== Updating Tickets ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Update status
    updated = pf.update_ticket(
        ticket_ids[0],
        status="in_progress",
        comment="Started investigation"
    )
    print(f"✓ Updated {updated.id}: status → {updated.status}")
    
    # Update multiple fields
    updated = pf.update_ticket(
        ticket_ids[1],
        priority="high",  # Escalated
        labels=["feature", "ui", "accessibility", "sprint-goal"]
    )
    print(f"✓ Updated {updated.id}: priority → {updated.priority}")
    print(f"                 labels → {updated.labels}")
    print()


def example_bulk_operations():
    """Bulk create tickets from external data."""
    print("=== Bulk Operations ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Import from external source (e.g., Jira, CSV, monitoring alerts)
    external_data = [
        {
            "title": "Database connection timeout",
            "description": "Intermittent timeouts during peak hours",
            "priority": "critical",
            "labels": ["bug"],
            "source_id": "JIRA-1234"
        },
        {
            "title": "Implement user search",
            "description": "Add fuzzy search to user directory",
            "priority": "medium",
            "labels": ["feature"]
        },
        {
            "title": "Refactor auth module",
            "description": "Reduce code complexity in auth.py",
            "priority": "low",
            "labels": ["chore"]
        }
    ]
    
    # Bulk create with source tracking
    created = pf.create_tickets_bulk(
        tickets_data=external_data,
        source="jira-migration",
        sprint="current"
    )
    
    print(f"✓ Bulk created {len(created)} tickets:\n")
    for t in created:
        print(f"  {t.id}: {t.title} [{t.priority}] - Labels: {t.labels}")
    print()
    
    return [t.id for t in created]


def example_delete_and_move(ticket_ids):
    """Delete and move tickets."""
    print("=== Delete and Move ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Move ticket to different sprint
    moved = pf.store.move_ticket(ticket_ids[0], to_sprint="backlog")
    print(f"✓ Moved {ticket_ids[0]} to backlog\n")
    
    # Delete a ticket (use with caution)
    # pf.store.delete_ticket(ticket_ids[-1])
    # print(f"✓ Deleted {ticket_ids[-1]}\n")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Planfile Python Library - Ticket Management")
    print("="*60 + "\n")
    
    ticket_ids = example_create_tickets()
    example_read_tickets(ticket_ids)
    example_update_tickets(ticket_ids)
    bulk_ids = example_bulk_operations()
    example_delete_and_move(ticket_ids)
    
    print("="*60)
    print("Ticket management examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
