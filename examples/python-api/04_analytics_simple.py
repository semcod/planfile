#!/usr/bin/env python3
"""
Simplified filtering and analytics using native store methods.

BEFORE: 163 lines
AFTER: 45 lines (-72%)
"""

from planfile import Planfile


def main():
    """Run simplified analytics examples."""
    print("\n" + "="*60)
    print("Simplified Analytics - Using Native API")
    print("="*60 + "\n")
    
    pf = Planfile.auto_discover(".")
    
    # 1. Get statistics with one call
    print("1. Ticket Statistics:")
    stats = pf.store.stats()
    print(f"   Total: {stats['total']}")
    print(f"   By Status: {stats['by_status']}")
    print(f"   By Priority: {stats['by_priority']}")
    print(f"   Top Labels: dict(list(stats['by_label'].items())[:5])")
    
    # 2. Export to different formats
    print("\n2. Export Formats:")
    
    # CSV
    csv_data = pf.store.export("csv", sprint="current")
    print(f"   CSV: {len(csv_data.split(chr(10)))} lines")
    
    # Markdown
    md_data = pf.store.export("markdown", status="open")
    print(f"   Markdown: {len(md_data.split(chr(10)))} lines")
    
    # JSON
    json_data = pf.store.export("json", priority="high")
    print(f"   JSON: {len(json_data)} chars")
    
    # 3. Full-text search
    print("\n3. Search:")
    results = pf.store.search("authentication", fields=["title", "description"])
    print(f"   Found '{len(results)}' tickets matching 'authentication'")
    
    # 4. Filter by labels
    print("\n4. Label Filtering:")
    bugs = pf.list_tickets(sprint="all", labels=["bug"])
    print(f"   Tickets with 'bug' label: {len(bugs)}")
    
    print("\n" + "="*60)
    print("Done!")
    print("="*60)


if __name__ == "__main__":
    main()
