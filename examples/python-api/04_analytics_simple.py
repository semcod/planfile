#!/usr/bin/env python3
"""Filtering and analytics using tickets returned by the public Python API."""

import csv
import io
import json
from collections import Counter

from demo_store import isolated_demo

from planfile import Planfile


@isolated_demo
def main():
    """Summarize and export a small disposable dataset."""
    pf = Planfile.auto_discover(".")
    pf.create_ticket(name="Example authentication bug", priority="high", labels=["bug", "backend"])
    tickets = pf.list_tickets()

    print("1. Ticket Statistics:")
    print(f"   Total: {len(tickets)}")
    print(f"   By Status: {dict(Counter(t.status for t in tickets))}")
    print(f"   By Priority: {dict(Counter(t.priority for t in tickets))}")
    print(f"   Top Labels: {Counter(label for t in tickets for label in t.labels).most_common(5)}")

    print("\n2. Export Formats:")
    csv_output = io.StringIO()
    writer = csv.writer(csv_output)
    writer.writerow(["id", "name", "priority"])
    writer.writerows((t.id, t.name, t.priority) for t in pf.list_tickets(sprint="current"))
    print(csv_output.getvalue())
    for ticket in pf.list_tickets(status="open"):
        print(f"- **{ticket.id}** {ticket.name}")
    print(json.dumps([t.model_dump(mode="json") for t in pf.list_tickets(priority="high")]))

    print("\n3. Search:")
    results = [t for t in tickets if "authentication" in f"{t.name} {t.description or ''}".lower()]
    print(f"   Found {len(results)} tickets matching 'authentication'")

    print("\n4. Label Filtering:")
    bugs = pf.list_tickets(sprint="all", labels=["bug"])
    print(f"   Tickets with 'bug' label: {len(bugs)}")


if __name__ == "__main__":
    main()
