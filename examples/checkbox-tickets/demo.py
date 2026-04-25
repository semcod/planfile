#!/usr/bin/env python3
"""Demo script showing planfile's checkbox ticket support."""

import tempfile
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from planfile.sync.markdown_backend import MarkdownFileBackend
from rich.console import Console
from rich.table import Table

console = Console()


def _build_summary_table(completed: list, pending: list) -> Table:
    """Build a summary table of ticket counts."""
    table = Table(title="Ticket Summary")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("IDs", style="dim")
    table.add_row(
        "✅ Completed",
        str(len(completed)),
        ", ".join([t.id[:20] + "..." for t in completed[:2]])
    )
    table.add_row(
        "⏳ Pending",
        str(len(pending)),
        ", ".join([t.id[:20] + "..." for t in pending[:2]])
    )
    return table


def _print_sample_tickets(tickets: list, label: str, icon: str, style: str) -> None:
    """Print a sample list of tickets with a style."""
    console.print(f"\n[bold]{label}:[/bold]")
    for t in tickets[:3]:
        console.print(f"  [{style}]{icon}[/{style}] {t.id}")


def _print_search_results(tickets: list, query: str) -> None:
    """Print search results for a query."""
    console.print(f"\n[bold]🔍 Searching for '{query}':[/bold]")
    for t in tickets[:3]:
        icon = "✓" if t.status == "completed" else "○"
        style = "green" if t.status == "completed" else "yellow"
        console.print(f"  [{style}]{icon}[/{style}] {t.id}")


def _print_toggle_demo(ticket) -> None:
    """Print toggle demo information."""
    console.print(f"\n[bold]🔄 Toggle Demo:[/bold]")
    console.print(f"  Ticket: {ticket.id}")
    console.print(f"  Current status: {ticket.status}")
    console.print(f"\n  [dim]To mark as completed, run:[/dim]")
    console.print(f"  [cyan]backend._toggle_checkbox_status('{ticket.id}', True)[/cyan]")


def demo_checkbox_tickets():
    """Demonstrate checkbox ticket parsing and manipulation."""
    console.print("\n[bold cyan]📝 Planfile Checkbox Tickets Demo[/bold cyan]\n")

    todo_path = Path(__file__).parent / "TODO.md"
    if not todo_path.exists():
        console.print("[red]❌ TODO.md not found![/red]")
        return

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Changelog\n\n")
        changelog_path = Path(f.name)

    try:
        backend = MarkdownFileBackend(
            changelog_file=str(changelog_path),
            todo_file=str(todo_path)
        )

        console.print("[bold]📋 Listing all tickets from TODO.md:[/bold]\n")
        tickets = backend._list_tickets()
        completed = [t for t in tickets if t.status == "completed"]
        pending = [t for t in tickets if t.status == "open"]

        console.print(_build_summary_table(completed, pending))
        _print_sample_tickets(completed, "📌 Sample Completed Tickets", "✓", "green")
        _print_sample_tickets(pending, "🕐 Sample Pending Tickets", "○", "yellow")
        _print_search_results(backend._search_tickets("magic"), "magic")

        if pending:
            _print_toggle_demo(pending[0])

        console.print("\n[bold green]✅ Demo completed successfully![/bold green]\n")
        console.print("[dim]Next steps:[/dim]")
        console.print("  1. Edit TODO.md to add/remove checkboxes")
        console.print("  2. Run: [cyan]planfile sync markdown[/cyan]")
        console.print("  3. Or use this backend in your own scripts!\n")

    finally:
        changelog_path.unlink(missing_ok=True)


if __name__ == "__main__":
    demo_checkbox_tickets()
