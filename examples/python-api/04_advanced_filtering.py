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
    print()


def example_combined_filters():
    """Combined filter criteria."""
    print("=== Combined Filters ===\n")
    
    pf = Planfile.auto_discover(".")
    
    # High priority open tickets in current sprint (using labels for categorization)
    urgent_tickets = pf.list_tickets(
        status="open",
        priority="high",
        sprint="current"
    )
    print(f"Urgent tickets in current sprint: {len(urgent_tickets)}")
    for t in urgent_tickets[:3]:
        print(f"  {t.id}: {t.title}")
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
    print("id,title,priority,labels")
    for t in sprint_tickets[:5]:
        labels_str = "|".join(t.labels) if t.labels else "none"
        print(f"{t.id},{t.title[:30]},{t.priority},{labels_str}")
    
    print("\nMarkdown Export:")
    print("## Sprint Tickets (High/Critical Priority)\n")
    for t in sprint_tickets[:5]:
        print(f"- **{t.id}** [{t.priority}] {t.title}")
        if t.labels:
            print(f"  - Labels: {', '.join(t.labels)}")
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
    
    # Count by labels (client-side)
    from collections import Counter
    all_labels = []
    for t in all_tickets:
        all_labels.extend(t.labels or [])
    label_counts = Counter(all_labels)
    print("\nBy Label:")
    for label, count in label_counts.most_common(10):
        print(f"  {label}: {count}")
    
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
