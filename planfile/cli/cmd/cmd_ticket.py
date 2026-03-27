"""Ticket management CLI commands — new in Sprint 3."""

import json
import sys
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

console = Console()


def _display_tickets(tickets, fmt: str = "table"):
    """Display tickets in the requested format."""
    if fmt == "json":
        console.print(json.dumps(
            [t.model_dump(mode="json", exclude_none=True) for t in tickets],
            indent=2, default=str))
        return
    if fmt == "yaml":
        console.print(yaml.dump(
            [t.model_dump(mode="json", exclude_none=True) for t in tickets],
            default_flow_style=False, sort_keys=False))
        return

    # table format
    if not tickets:
        console.print("[dim]No tickets found.[/dim]")
        return

    table = Table(title=f"Tickets ({len(tickets)})")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    table.add_column("Priority")
    table.add_column("Title")
    table.add_column("Labels", style="dim")
    table.add_column("Source", style="dim")

    status_colors = {
        "open": "white", "in_progress": "yellow",
        "review": "blue", "done": "green", "blocked": "red",
    }
    priority_colors = {
        "critical": "red bold", "high": "red",
        "normal": "white", "low": "dim",
    }

    for t in tickets:
        status_val = t.status.value if hasattr(t.status, 'value') else str(t.status)
        sc = status_colors.get(status_val, "white")
        pc = priority_colors.get(t.priority, "white")
        source_str = t.source.tool if t.source else ""
        table.add_row(
            t.id,
            f"[{sc}]{status_val}[/{sc}]",
            f"[{pc}]{t.priority}[/{pc}]",
            t.title,
            ", ".join(t.labels) if t.labels else "",
            source_str,
        )

    console.print(table)


def register_ticket_commands(app: typer.Typer) -> None:
    """Register ticket subcommands on the typer app."""

    ticket_app = typer.Typer(help="Manage tickets")

    @ticket_app.command("create")
    def ticket_create(
        title: str = typer.Argument(..., help="Ticket title"),
        priority: str = typer.Option("normal", "-p", "--priority",
                                     help="critical | high | normal | low"),
        sprint: str = typer.Option("current", "-s", "--sprint"),
        source: str = typer.Option("human", help="Source tool name"),
        label: Optional[list[str]] = typer.Option(None, "-l", "--label"),
        description: str = typer.Option("", "-d", "--description"),
    ):
        """Create a new ticket."""
        from planfile import Planfile, TicketSource
        pf = Planfile.auto_discover()
        ticket = pf.create_ticket(
            title=title, priority=priority, sprint=sprint,
            source=TicketSource(tool=source),
            labels=list(label) if label else [],
            description=description,
        )
        console.print(f"[green]✓[/green] Created {ticket.id}: {ticket.title}")

    @ticket_app.command("list")
    def ticket_list(
        sprint: str = typer.Option("current", "-s", "--sprint"),
        status: Optional[str] = typer.Option(None, help="open|in_progress|review|done|blocked|all"),
        source: Optional[str] = typer.Option(None, help="Filter by source tool"),
        label: Optional[list[str]] = typer.Option(None, "-l", "--label"),
        fmt: str = typer.Option("table", "--format", help="table | json | yaml"),
    ):
        """List tickets with optional filters."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        filters = {}
        if status and status != "all":
            filters["status"] = status
        if source:
            filters["source"] = source
        if label:
            filters["labels"] = list(label)
        tickets = pf.list_tickets(sprint=sprint, **filters)
        _display_tickets(tickets, fmt)

    @ticket_app.command("show")
    def ticket_show(
        ticket_id: str = typer.Argument(..., help="Ticket ID (e.g. PLF-001)"),
        fmt: str = typer.Option("yaml", "--format", help="yaml | json"),
    ):
        """Show details of a single ticket."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        ticket = pf.get_ticket(ticket_id)
        if not ticket:
            console.print(f"[red]✗[/red] Ticket {ticket_id} not found.")
            raise typer.Exit(1)
        data = ticket.model_dump(mode="json", exclude_none=True)
        if fmt == "json":
            console.print(json.dumps(data, indent=2, default=str))
        else:
            console.print(yaml.dump(data, default_flow_style=False, sort_keys=False))

    @ticket_app.command("update")
    def ticket_update(
        ticket_id: str = typer.Argument(..., help="Ticket ID"),
        status: Optional[str] = typer.Option(None, help="New status"),
        priority: Optional[str] = typer.Option(None, "-p", "--priority"),
        title: Optional[str] = typer.Option(None, help="New title"),
    ):
        """Update ticket fields."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        updates = {}
        if status:
            updates["status"] = status
        if priority:
            updates["priority"] = priority
        if title:
            updates["title"] = title
        if not updates:
            console.print("[yellow]⚠[/yellow] No updates specified.")
            raise typer.Exit(1)
        ticket = pf.update_ticket(ticket_id, **updates)
        if not ticket:
            console.print(f"[red]✗[/red] Ticket {ticket_id} not found.")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Updated {ticket.id}")

    @ticket_app.command("move")
    def ticket_move(
        ticket_id: str = typer.Argument(..., help="Ticket ID"),
        to_sprint: str = typer.Argument(..., help="Target sprint"),
    ):
        """Move ticket to another sprint."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        ok = pf.store.move_ticket(ticket_id, to_sprint)
        if ok:
            console.print(f"[green]✓[/green] Moved {ticket_id} → {to_sprint}")
        else:
            console.print(f"[red]✗[/red] Ticket {ticket_id} not found.")
            raise typer.Exit(1)

    @ticket_app.command("import")
    def ticket_import(
        source: str = typer.Option(..., help="Source tool name"),
        sprint: str = typer.Option("current", "-s", "--sprint"),
        from_file: Optional[str] = typer.Option(None, "--from", help="Import from file"),
    ):
        """Import tickets from tool output (stdin JSON or file)."""
        from planfile import Planfile
        pf = Planfile.auto_discover()

        if from_file:
            try:
                from planfile.importers import import_from_source
                tickets = import_from_source(from_file, source=source)
            except ImportError:
                # Importers not yet available — fallback to JSON
                with open(from_file) as f:
                    data = json.load(f)
                tickets = data if isinstance(data, list) else [data]
        else:
            data = json.load(sys.stdin)
            tickets = data if isinstance(data, list) else [data]

        created = pf.create_tickets_bulk(tickets, source=source, sprint=sprint)
        console.print(f"[green]✓[/green] Created {len(created)} tickets from {source}")

    app.add_typer(ticket_app, name="ticket")
