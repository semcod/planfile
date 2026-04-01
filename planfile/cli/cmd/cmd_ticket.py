"""Ticket management CLI commands — new in Sprint 3."""

import json
import sys

import typer
import yaml
from rich.console import Console
from rich.table import Table

console = Console()


def _display_tickets(tickets, fmt: str = "table") -> None:
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
        label: list[str] | None = typer.Option(None, "-l", "--label"),
        description: str = typer.Option("", "-d", "--description"),
        integration: list[str] | None = typer.Option(None, "-i", "--integration",
                                                     help="Integration(s) to sync with (e.g., github, gitlab)"),
    ) -> None:
        """Create a new ticket."""
        from planfile import Planfile, TicketSource
        pf = Planfile.auto_discover()
        ticket_data = {
            "title": title,
            "priority": priority,
            "sprint": sprint,
            "source": TicketSource(tool=source),
            "labels": list(label) if label else [],
            "description": description,
        }
        if integration:
            ticket_data["integration"] = list(integration)
        ticket = pf.create_ticket(**ticket_data)
        console.print(f"[green]✓[/green] Created {ticket.id}: {ticket.title}")

    @ticket_app.command("list")
    def ticket_list(
        sprint: str = typer.Option("current", "-s", "--sprint"),
        status: str | None = typer.Option(None, help="open|in_progress|review|done|blocked|all"),
        source: str | None = typer.Option(None, help="Filter by source tool"),
        label: list[str] | None = typer.Option(None, "-l", "--label"),
        fmt: str = typer.Option("table", "--format", help="table | json | yaml"),
    ) -> None:
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
    ) -> None:
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
        status: str | None = typer.Option(None, help="New status"),
        priority: str | None = typer.Option(None, "-p", "--priority"),
        title: str | None = typer.Option(None, help="New title"),
    ) -> None:
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
    ) -> None:
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
        from_file: str | None = typer.Option(None, "--from", help="Import from file"),
    ) -> None:
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

    @ticket_app.command("done")
    def ticket_done(
        ticket_id: str = typer.Argument(..., help="Ticket ID to mark as done"),
    ) -> None:
        """Mark ticket as done (shortcut for update --status done)."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        ticket = pf.update_ticket(ticket_id, status="done")
        if not ticket:
            console.print(f"[red]✗[/red] Ticket {ticket_id} not found.")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Marked {ticket.id} as [green]done[/green]")

    @ticket_app.command("start")
    def ticket_start(
        ticket_id: str = typer.Argument(..., help="Ticket ID to start working on"),
    ) -> None:
        """Mark ticket as in_progress (shortcut for update --status in_progress)."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        ticket = pf.update_ticket(ticket_id, status="in_progress")
        if not ticket:
            console.print(f"[red]✗[/red] Ticket {ticket_id} not found.")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Started {ticket.id} → [yellow]in_progress[/yellow]")

    @ticket_app.command("block")
    def ticket_block(
        ticket_id: str = typer.Argument(..., help="Ticket ID to block"),
        reason: str = typer.Option(None, "-r", "--reason", help="Block reason"),
    ) -> None:
        """Mark ticket as blocked (shortcut for update --status blocked)."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        updates = {"status": "blocked"}
        if reason:
            updates["description"] = f"BLOCKED: {reason}"
        ticket = pf.update_ticket(ticket_id, **updates)
        if not ticket:
            console.print(f"[red]✗[/red] Ticket {ticket_id} not found.")
            raise typer.Exit(1)
        console.print(f"[red]🚫[/red] Blocked {ticket.id}")

    @ticket_app.command("review")
    def ticket_review(
        ticket_id: str = typer.Argument(..., help="Ticket ID to send for review"),
    ) -> None:
        """Mark ticket as ready for review (shortcut for update --status review)."""
        from planfile import Planfile
        pf = Planfile.auto_discover()
        ticket = pf.update_ticket(ticket_id, status="review")
        if not ticket:
            console.print(f"[red]✗[/red] Ticket {ticket_id} not found.")
            raise typer.Exit(1)
        console.print(f"[blue]👀[/blue] Sent {ticket.id} to [blue]review[/blue]")

    @ticket_app.command("import-todo")
    def ticket_import_todo(
        todo_file: str = typer.Option("TODO.md", "--file", help="TODO.md file path"),
        sprint: str = typer.Option("current", "-s", "--sprint"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without importing"),
    ) -> None:
        """Import tickets from TODO.md checkbox items into planfile."""
        from planfile import Planfile
        from pathlib import Path
        import re

        pf = Planfile.auto_discover()
        todo_path = Path(todo_file)

        if not todo_path.exists():
            console.print(f"[red]✗[/red] File not found: {todo_file}")
            raise typer.Exit(1)

        content = todo_path.read_text(encoding="utf-8")
        lines = content.split('\n')

        imported = 0
        skipped = 0

        for line_num, line in enumerate(lines, 1):
            # Match checkbox lines: - [ ] or - [x]
            match = re.match(r'^(\s*)-\s*\[([ xX])\]\s*(.+)$', line)
            if match:
                is_checked = match.group(2).lower() == 'x'
                task_text = match.group(3).strip()

                if not task_text:
                    continue

                # Determine priority from prefix emojis
                priority = "normal"
                if task_text.startswith('🔴'):
                    priority = "critical"
                    task_text = task_text[2:].strip()
                elif task_text.startswith('🟠'):
                    priority = "high"
                    task_text = task_text[2:].strip()
                elif task_text.startswith('🟡'):
                    priority = "medium"
                    task_text = task_text[2:].strip()
                elif task_text.startswith('🟢'):
                    priority = "low"
                    task_text = task_text[2:].strip()
                elif task_text.startswith('⚪'):
                    priority = "normal"
                    task_text = task_text[2:].strip()

                # Skip if already exists (check by title)
                existing = [t for t in pf.list_tickets(sprint=sprint) if t.title == task_text]
                if existing:
                    skipped += 1
                    continue

                if dry_run:
                    status_str = "done" if is_checked else "open"
                    console.print(f"  Would import: [{status_str}] {task_text}")
                else:
                    ticket = pf.create_ticket(
                        title=task_text,
                        priority=priority,
                        sprint=sprint,
                        status="done" if is_checked else "open",
                        source={"tool": "todo-import", "context": {"source_file": todo_file, "line": line_num}}
                    )
                    console.print(f"  [green]✓[/green] Imported {ticket.id}: {ticket.title[:50]}")
                    imported += 1

        if dry_run:
            console.print(f"\n[cyan]🔍 Dry run — would import {imported} tickets[/cyan]")
        else:
            console.print(f"\n[green]✓[/green] Imported {imported} tickets, skipped {skipped} duplicates")

    @ticket_app.command("export-todo")
    def ticket_export_todo(
        todo_file: str = typer.Option("TODO.md", "--file", help="TODO.md file path"),
        sprint: str = typer.Option("all", "-s", "--sprint", help="Sprint to export (current/backlog/all)"),
        include_done: bool = typer.Option(True, "--include-done/--skip-done"),
    ) -> None:
        """Export planfile tickets to TODO.md format."""
        from planfile import Planfile
        from pathlib import Path
        from datetime import datetime

        pf = Planfile.auto_discover()

        # Get tickets
        if sprint == "all":
            tickets = pf.list_tickets(sprint="all")
        else:
            tickets = pf.list_tickets(sprint=sprint)

        if not include_done:
            tickets = [t for t in tickets if t.status != "done"]

        # Sort: open/in_progress first, then done
        status_order = {"open": 0, "in_progress": 1, "review": 2, "blocked": 3, "done": 4}
        tickets.sort(key=lambda t: (status_order.get(str(t.status), 5), t.priority != "critical", t.priority != "high"))

        # Generate TODO.md content
        lines = [
            "# TODO",
            "",
            "<!-- AUTO-GENERATED FROM PLANFILE - DO NOT EDIT DIRECTLY -->",
            "<!-- Use: planfile ticket export-todo to regenerate -->",
            "<!-- Use: planfile ticket import-todo to import changes -->",
            f"<!-- Generated: {datetime.now().isoformat()} -->",
            "",
        ]

        # Priority emoji mapping
        priority_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "normal": "⚪"
        }

        # Group by status - handle both Enum and string status
        def get_status_value(t):
            status = t.status
            return status.value if hasattr(status, 'value') else str(status)

        pending = [t for t in tickets if get_status_value(t) != "done"]
        done = [t for t in tickets if get_status_value(t) == "done"]

        if pending:
            lines.append("## Active Tasks")
            lines.append("")
            for t in pending:
                emoji = priority_emoji.get(t.priority, "⚪")
                checkbox = "[ ]"
                lines.append(f"- {checkbox} {emoji} [{t.id}] {t.title}")
            lines.append("")

        if done and include_done:
            lines.append("## Completed Tasks")
            lines.append("")
            for t in done:
                emoji = priority_emoji.get(t.priority, "⚪")
                lines.append(f"- [x] {emoji} [{t.id}] {t.title}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("**Note:** This file is auto-generated from planfile. To modify tickets:")
        lines.append("1. Use `planfile ticket create/update/done/start/block` commands")
        lines.append("2. Or edit tickets in `.planfile/sprints/` and run `planfile ticket export-todo`")
        lines.append("")

        # Write file
        todo_path = Path(todo_file)
        todo_path.write_text('\n'.join(lines), encoding="utf-8")

        console.print(f"[green]✓[/green] Exported {len(pending)} pending, {len(done)} done tickets to {todo_file}")

    app.add_typer(ticket_app, name="ticket")
