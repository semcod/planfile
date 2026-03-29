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


def demo_checkbox_tickets():
    """Demonstrate checkbox ticket parsing and manipulation."""
    
    console.print("\n[bold cyan]📝 Planfile Checkbox Tickets Demo[/bold cyan]\n")
    
    # Read the example TODO.md
    todo_path = Path(__file__).parent / "TODO.md"
    
    if not todo_path.exists():
        console.print("[red]❌ TODO.md not found![/red]")
        return
    
    # Create temporary CHANGELOG.md
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Changelog\n\n")
        changelog_path = Path(f.name)
    
    try:
        # Initialize backend
        backend = MarkdownFileBackend(
            changelog_file=str(changelog_path),
            todo_file=str(todo_path)
        )
        
        # List all tickets
        console.print("[bold]📋 Listing all tickets from TODO.md:[/bold]\n")
        tickets = backend._list_tickets()
        
        # Separate by status
        completed = [t for t in tickets if t.status == "completed"]
        pending = [t for t in tickets if t.status == "open"]
        
        # Show summary table
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
        
        console.print(table)
        
        # Show sample tickets
        console.print("\n[bold]📌 Sample Completed Tickets:[/bold]")
        for t in completed[:3]:
            console.print(f"  [green]✓[/green] {t.id}")
            
        console.print("\n[bold]🕐 Sample Pending Tickets:[/bold]")
        for t in pending[:3]:
            console.print(f"  [yellow]○[/yellow] {t.id}")
        
        # Demonstrate search
        console.print("\n[bold]🔍 Searching for 'magic':[/bold]")
        magic_tickets = backend._search_tickets("magic")
        for t in magic_tickets[:3]:
            icon = "✓" if t.status == "completed" else "○"
            console.print(f"  [{ 'green' if t.status == 'completed' else 'yellow' }]{icon}[/{ 'green' if t.status == 'completed' else 'yellow' }] {t.id}")
        
        # Demonstrate status toggle (on a copy)
        if pending:
            test_ticket = pending[0]
            console.print(f"\n[bold]🔄 Toggle Demo:[/bold]")
            console.print(f"  Ticket: {test_ticket.id}")
            console.print(f"  Current status: {test_ticket.status}")
            
            # Show how to toggle (but don't actually modify the example file)
            console.print(f"\n  [dim]To mark as completed, run:[/dim]")
            console.print(f"  [cyan]backend._toggle_checkbox_status('{test_ticket.id}', True)[/cyan]")
        
        console.print("\n[bold green]✅ Demo completed successfully![/bold green]\n")
        
        console.print("[dim]Next steps:[/dim]")
        console.print("  1. Edit TODO.md to add/remove checkboxes")
        console.print("  2. Run: [cyan]planfile sync markdown[/cyan]")
        console.print("  3. Or use this backend in your own scripts!\n")
        
    finally:
        # Cleanup
        changelog_path.unlink(missing_ok=True)


if __name__ == "__main__":
    demo_checkbox_tickets()
