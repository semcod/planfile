#!/usr/bin/env python3
"""
Advanced filtering and search operations.

Shows how to:
- Filter tickets by multiple criteria
- Search tickets by content
- Export filtered results
"""

from datetime import datetime, timedelta
from planfile import Planfile


def example_basic_filtering():
    """Basic ticket filtering."""
    print("=== Basic Filtering ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Filter by status
    open_tickets = pf.list_tickets(status="open")
    print(f"Open tickets: {len(open_tickets)}")
    
    # Filter by priority
    critical = pf.list_tickets(priority="critical")
    print(f"Critical priority: {len(critical)}")
    
    high_priority = pf.list_tickets(priority="high")
    print(f"High priority: {len(high_priority)}")
    
    # Filter by sprint
    current_sprint = pf.list_tickets(sprint="current")
    print(f"Current sprint: {len(current_sprint)}")
    
    # Filter by assignee
    my_tickets = pf.list_tickets(assignee="john.doe")
    print(f"Assigned to john.doe: {len(my_tickets)}")
    print()


def example_combined_filters():
    """Combined filter criteria."""
    print("=== Combined Filters ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # High priority bugs in current sprint
    urgent_bugs = pf.list_tickets(
        status="open",
        priority="high",
        type="bug",
        sprint="current"
    )
    print(f"Urgent bugs in current sprint: {len(urgent_bugs)}")
    for t in urgent_bugs[:3]:
        print(f"  {t.id}: {t.title}")
    print()
    
    # Unassigned tickets
    unassigned = pf.list_tickets(assignee=None, status="open")
    print(f"Unassigned open tickets: {len(unassigned)}")
    print()


def example_search_by_labels():
    """Search by labels and tags."""
    print("=== Label-based Search ===\n")
    
    pf = Planfile.auto_discover(".")
    
    all_tickets = pf.list_tickets()
    
    # Filter by labels (client-side)
    backend_tickets = [t for t in all_tickets if "backend" in (t.labels or [])]
    print(f"Backend-related tickets: {len(backend_tickets)}")
    
    security_tickets = [t for t in all_tickets if "security" in (t.labels or [])]
    print(f"Security tickets: {len(security_tickets)}")
    
    # Multiple labels
    critical_backend = [
        t for t in all_tickets 
        if "backend" in (t.labels or []) and "critical" in (t.labels or [])
    ]
    print(f"Critical backend tickets: {len(critical_backend)}")
    print()


def example_export_filtered():
    """Export filtered results to various formats."""
    print("=== Export Filtered Results ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # Get high priority open tickets for sprint planning
    sprint_tickets = pf.list_tickets(
        sprint="current",
        status="open",
        priority=["high", "critical"]
    )
    
    # Export to CSV format
    print("CSV Export:")
    print("id,title,priority,type,assignee")
    for t in sprint_tickets[:5]:
        print(f"{t.id},{t.title[:30]},{t.priority},{t.type or 'task'},{t.assignee or 'unassigned'}")
    
    print("\nMarkdown Export:")
    print("## Sprint Tickets (High/Critical Priority)\n")
    for t in sprint_tickets[:5]:
        print(f"- **{t.id}** [{t.priority}] {t.title}")
        if t.assignee:
            print(f"  - Assignee: @{t.assignee}")
    print()


def example_statistics():
    """Generate ticket statistics."""
    print("=== Ticket Statistics ===\n")
    
    pf = Planfile.auto_discover(".")
    all_tickets = pf.list_tickets()
    
    # Count by status
    from collections import Counter
    
    status_counts = Counter(t.status for t in all_tickets)
    print("By Status:")
    for status, count in status_counts.most_common():
        print(f"  {status}: {count}")
    
    # Count by priority
    priority_counts = Counter(t.priority for t in all_tickets)
    print("\nBy Priority:")
    for priority, count in priority_counts.most_common():
        print(f"  {priority}: {count}")
    
    # Count by type
    type_counts = Counter(t.type for t in all_tickets if t.type)
    print("\nBy Type:")
    for ttype, count in type_counts.most_common():
        print(f"  {ttype}: {count}")
    
    print()


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Planfile Python Library - Advanced Filtering")
    print("="*60 + "\n")
    
    example_basic_filtering()
    example_combined_filters()
    example_search_by_labels()
    example_export_filtered()
    example_statistics()
    
    print("="*60)
    print("Filtering examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
