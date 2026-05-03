"""Ticket management CLI commands."""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.table import Table
from planfile.cli.core import console


def _auto_sync(directory: str, integrations: list[str] | None = None, dry_run: bool = False) -> None:
    """Auto-sync changes to configured integrations after ticket modification."""
    from planfile.cli.groups.sync.core import sync_integration
    from planfile.integrations.config import IntegrationConfig
    
    config = IntegrationConfig(directory)
    config.load_configs()
    
    # Determine which integrations to sync
    if integrations:
        to_sync = integrations
    else:
        # Sync all configured integrations
        to_sync = list(config.config.get("integrations", {}).keys())
        # Always include markdown as fallback
        if "markdown" not in to_sync:
            to_sync.append("markdown")
    
    if not to_sync:
        console.print("[dim]ℹ️ No integrations configured for auto-sync[/dim]")
        return
    
    console.print(f"\n[blue]🔄 Auto-syncing to: {', '.join(to_sync)}...[/blue]")
    
    for integration in to_sync:
        try:
            sync_integration(integration, directory, dry_run, "to", show_header=False)
        except Exception as e:
            console.print(f"[yellow]⚠️ Auto-sync failed for {integration}: {e}[/yellow]")

def _display_tickets(tickets, fmt: str='table') -> None:
    """Display tickets in the requested format."""
    if fmt == 'json':
        console.print(json.dumps([t.model_dump(mode='json', exclude_none=True) for t in tickets], indent=2, default=str))
        return
    if fmt == 'yaml':
        console.print(yaml.dump([t.model_dump(mode='json', exclude_none=True) for t in tickets], default_flow_style=False, sort_keys=False))
        return
    if not tickets:
        console.print('[dim]No tickets found.[/dim]')
        return
    table = create_ticket_table(tickets)
    console.print(table)


def _load_issue_records_from_file(issues_path: str | None) -> list[dict] | None:
    """Load optional issue records from a YAML/JSON file."""
    if not issues_path:
        return None

    path = Path(issues_path)
    if not path.exists():
        console.print(f"[red]✗[/red] Issues file not found: {issues_path}")
        raise typer.Exit(1)

    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read issues file: {e}")
        raise typer.Exit(1)

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        for key in ('issues', 'errors', 'findings', 'results', 'messages'):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def _print_ticket_validation_table(tickets: list[dict]) -> None:
    """Print ticket validation results in table format."""
    if not tickets:
        console.print('[dim]No matching tickets to validate.[/dim]')
        return

    table = Table(title=f'Ticket Validation ({len(tickets)})')
    table.add_column('ID', style='cyan', no_wrap=True)
    table.add_column('Status', style='bold')
    table.add_column('Reason')
    table.add_column('Files', style='dim')

    status_colors = {'current': 'green', 'stale': 'red', 'unknown': 'yellow'}

    for ticket in tickets:
        status = str(ticket.get('status', 'unknown'))
        ticket_id = str(ticket.get('ticket_id', 'unknown'))
        reason = str(ticket.get('reason', ''))
        files = ', '.join(ticket.get('files') or [])
        color = status_colors.get(status, 'white')
        table.add_row(ticket_id, f'[{color}]{status}[/{color}]', reason, files)

    console.print(table)


def ticket_validate(
    ticket_ids: list[str] = typer.Argument(None, help='Optional ticket ID(s) to validate (e.g., Q01 PLF-002)'),
    strategy: str = typer.Option('planfile.yaml', '--strategy', '-S', help='Path to strategy/planfile YAML'),
    project: str = typer.Option('.', '--project', '-p', help='Project root directory'),
    issues: str | None = typer.Option(None, '--issues', '-e', help='Optional YAML/JSON issue scan file'),
    fmt: str = typer.Option('table', '--format', help='table | json | yaml'),
    stale_only: bool = typer.Option(False, '--stale-only', help='Show only stale tickets in output'),
    fail_on_stale: bool = typer.Option(False, '--fail-on-stale', help='Exit with code 1 if stale tickets are found'),
) -> None:
    """Validate whether planfile tickets are still current against code and scan data."""
    from planfile import validate_planfile_tickets

    issue_records = _load_issue_records_from_file(issues)
    report = validate_planfile_tickets(
        strategy_path=strategy,
        project_path=project,
        issue_records=issue_records,
        ticket_ids=ticket_ids or None,
    )

    visible_tickets = report.get('tickets', [])
    if stale_only:
        visible_tickets = [ticket for ticket in visible_tickets if ticket.get('status') == 'stale']

    if fmt == 'json':
        payload = dict(report)
        payload['tickets'] = visible_tickets
        console.print(json.dumps(payload, indent=2, default=str))
    elif fmt == 'yaml':
        payload = dict(report)
        payload['tickets'] = visible_tickets
        console.print(yaml.dump(payload, default_flow_style=False, sort_keys=False))
    elif fmt == 'table':
        console.print(
            f"[bold]Validation:[/bold] total={report.get('total', 0)} "
            f"current={report.get('current', 0)} stale={report.get('stale', 0)} "
            f"unknown={report.get('unknown', 0)}"
        )
        _print_ticket_validation_table(visible_tickets)
    else:
        console.print(f"[red]✗[/red] Unsupported format: {fmt}")
        raise typer.Exit(1)

    if fail_on_stale and int(report.get('stale', 0)) > 0:
        raise typer.Exit(1)

def create_ticket_table(tickets) -> Table:
    """Create and populate a Rich table for displaying tickets."""
    table = Table(title=f'Tickets ({len(tickets)})')
    table.add_column('ID', style='cyan', no_wrap=True)
    table.add_column('Status', style='bold')
    table.add_column('Priority')
    table.add_column('Name')
    table.add_column('Labels', style='dim')
    table.add_column('Source', style='dim')
    status_colors = {'open': 'white', 'in_progress': 'yellow', 'review': 'blue', 'done': 'green', 'blocked': 'red'}
    priority_colors = {'critical': 'red bold', 'high': 'red', 'normal': 'white', 'low': 'dim'}
    for t in tickets:
        status_val = t.status.value if hasattr(t.status, 'value') else str(t.status)
        sc = status_colors.get(status_val, 'white')
        pc = priority_colors.get(t.priority, 'white')
        source_str = t.source.tool if t.source else ''
        table.add_row(t.id, f'[{sc}]{status_val}[/{sc}]', f'[{pc}]{t.priority}[/{pc}]', t.name, ', '.join(t.labels) if t.labels else '', source_str)
    return table

def ticket_create(name: str=typer.Argument(..., help='Ticket name'), priority: str=typer.Option('normal', '-p', '--priority', help='critical | high | normal | low'), sprint: str=typer.Option('current', '-s', '--sprint'), source: str=typer.Option('human', help='Source tool name'), label: list[str] | None=typer.Option(None, '-l', '--label'), description: str=typer.Option('', '-d', '--description'), files: list[str] | None=typer.Option(None, '--files', help='File(s) associated with this ticket'), integration: list[str] | None=typer.Option(None, '-i', '--integration', help='Integration(s) to sync with (e.g., github, gitlab)'), sync: bool=typer.Option(False, '--sync', help='Auto-sync to configured integrations after creation'), sync_dry_run: bool=typer.Option(False, '--sync-dry-run', help='Preview sync without making changes')) -> None:
    """Create a new ticket."""
    from planfile import Planfile, TicketSource
    pf = Planfile.auto_discover()
    ticket_data = {'name': name, 'priority': priority, 'sprint': sprint, 'source': TicketSource(tool=source), 'labels': list(label) if label else [], 'description': description}
    if files:
        ticket_data['files'] = list(files)
    if integration:
        ticket_data['integration'] = list(integration)
    ticket = pf.create_ticket(**ticket_data)
    console.print(f'[green]✓[/green] Created {ticket.id}: {ticket.name}')
    
    if sync:
        _auto_sync(str(pf.store.project_dir), integration, sync_dry_run)

def ticket_list(sprint: str=typer.Option('current', '-s', '--sprint'), status: str | None=typer.Option(None, help='open|in_progress|review|done|blocked|all'), source: str | None=typer.Option(None, help='Filter by source tool'), label: list[str] | None=typer.Option(None, '-l', '--label'), files: list[str] | None=typer.Option(None, '--files', help='Filter by file glob pattern(s)'), fmt: str=typer.Option('table', '--format', help='table | json | yaml')) -> None:
    """List tickets with optional filters."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    filters = {}
    if status and status != 'all':
        filters['status'] = status
    if source:
        filters['source'] = source
    if label:
        filters['labels'] = list(label)
    if files:
        filters['files'] = files
    tickets = pf.list_tickets(sprint=sprint, **filters)
    _display_tickets(tickets, fmt)

def ticket_show(ticket_id: str=typer.Argument(..., help='Ticket ID (e.g. PLF-001)'), fmt: str=typer.Option('yaml', '--format', help='yaml | json')) -> None:
    """Show details of a single ticket."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    ticket = pf.get_ticket(ticket_id)
    if not ticket:
        console.print(f'[red]✗[/red] Ticket {ticket_id} not found.')
        raise typer.Exit(1)
    data = ticket.model_dump(mode='json', exclude_none=True)
    if fmt == 'json':
        console.print(json.dumps(data, indent=2, default=str))
    else:
        console.print(yaml.dump(data, default_flow_style=False, sort_keys=False))

def ticket_update(ticket_id: str=typer.Argument(..., help='Ticket ID'), status: str | None=typer.Option(None, help='New status'), priority: str | None=typer.Option(None, '-p', '--priority'), name: str | None=typer.Option(None, help='New name'), sync: bool=typer.Option(False, '--sync', help='Auto-sync to configured integrations after update'), sync_dry_run: bool=typer.Option(False, '--sync-dry-run', help='Preview sync without making changes')) -> None:
    """Update ticket fields."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    updates = {}
    if status:
        updates['status'] = status
    if priority:
        updates['priority'] = priority
    if name:
        updates['name'] = name
    if not updates:
        console.print('[yellow]⚠[/yellow] No updates specified.')
        raise typer.Exit(1)
    ticket = pf.update_ticket(ticket_id, **updates)
    if not ticket:
        console.print(f'[red]✗[/red] Ticket {ticket_id} not found.')
        raise typer.Exit(1)
    console.print(f'[green]✓[/green] Updated {ticket.id}')
    
    if sync:
        _auto_sync(str(pf.store.project_dir), None, sync_dry_run)

def ticket_move(ticket_id: str=typer.Argument(..., help='Ticket ID'), to_sprint: str=typer.Argument(..., help='Target sprint')) -> None:
    """Move ticket to another sprint."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    ok = pf.store.move_ticket(ticket_id, to_sprint)
    if ok:
        console.print(f'[green]✓[/green] Moved {ticket_id} → {to_sprint}')
    else:
        console.print(f'[red]✗[/red] Ticket {ticket_id} not found.')
        raise typer.Exit(1)

def ticket_import(source: str=typer.Option(..., help='Source tool name'), sprint: str=typer.Option('current', '-s', '--sprint'), from_file: str | None=typer.Option(None, '--from', help='Import from file')) -> None:
    """Import tickets from tool output (stdin JSON or file)."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    tickets = load_import_tickets(from_file, source)
    created = pf.create_tickets_bulk(tickets, source=source, sprint=sprint)
    console.print(f'[green]✓[/green] Created {len(created)} tickets from {source}')

def load_import_tickets(from_file: str | None, source: str) -> list:
    """Load tickets data from file or stdin."""
    if from_file:
        try:
            from planfile.importers import import_from_source
            tickets = import_from_source(from_file, source=source)
        except ImportError:
            with open(from_file) as f:
                data = json.load(f)
            tickets = data if isinstance(data, list) else [data]
    else:
        data = json.load(sys.stdin)
        tickets = data if isinstance(data, list) else [data]
    return tickets

def ticket_done(ticket_id: str=typer.Argument(..., help='Ticket ID to mark as done')) -> None:
    """Mark ticket as done (shortcut for update --status done)."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    ticket = pf.update_ticket(ticket_id, status='done')
    if not ticket:
        console.print(f'[red]✗[/red] Ticket {ticket_id} not found.')
        raise typer.Exit(1)
    console.print(f'[green]✓[/green] Marked {ticket.id} as [green]done[/green]')

def ticket_start(ticket_id: str=typer.Argument(..., help='Ticket ID to start working on')) -> None:
    """Mark ticket as in_progress (shortcut for update --status in_progress)."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    ticket = pf.update_ticket(ticket_id, status='in_progress')
    if not ticket:
        console.print(f'[red]✗[/red] Ticket {ticket_id} not found.')
        raise typer.Exit(1)
    console.print(f'[green]✓[/green] Started {ticket.id} → [yellow]in_progress[/yellow]')

def ticket_block(ticket_id: str=typer.Argument(..., help='Ticket ID to block'), reason: str=typer.Option(None, '-r', '--reason', help='Block reason')) -> None:
    """Mark ticket as blocked (shortcut for update --status blocked)."""
    from planfile import Planfile
    pf = Planfile.auto_discover()
    updates = {'status': 'blocked'}
    if reason:
        updates['description'] = f'BLOCKED: {reason}'
    ticket = pf.update_ticket(ticket_id, **updates)
    if not ticket:
        console.print(f'[red]✗[/red] Ticket {ticket_id} not found.')
        raise typer.Exit(1)
    console.print(f'[green]✓[/green] Blocked {ticket.id}')

def _collect_delete_ids(
    pf: Any,
    ticket_ids: list[str] | None,
    sprint: str | None,
    status: str | None,
    label: list[str] | None,
    source: str | None,
    files: list[str] | None,
) -> list[str]:
    to_delete: list[str] = list(ticket_ids or [])
    if sprint or status or label or source or files:
        filters: dict = {}
        if status:
            filters['status'] = status
        if source:
            filters['source'] = source
        if label:
            filters['labels'] = list(label)
        if files:
            filters['files'] = files
        sprint_arg = sprint if sprint else 'all'
        for t in pf.list_tickets(sprint=sprint_arg, **filters):
            if t.id not in to_delete:
                to_delete.append(t.id)
    return to_delete


def _confirm_and_delete(
    pf: Any, to_delete: list[str], dry_run: bool, force: bool
) -> tuple[list[str], list[str]]:
    console.print(f'[bold]Tickets to delete:[/bold] ({len(to_delete)} total)')
    for tid in sorted(to_delete):
        console.print(f'  - {tid}')
    if dry_run:
        console.print('[cyan]--dry-run[/cyan]: No tickets were deleted.')
        raise typer.Exit(0)
    if not force:
        if not typer.confirm(f'Delete {len(to_delete)} ticket(s)?'):
            console.print('[dim]Cancelled.[/dim]')
            raise typer.Exit(0)
    return pf.delete_tickets(to_delete)


def ticket_delete(
    ticket_ids: list[str] = typer.Argument(None, help='Ticket ID(s) to delete (e.g., PLF-001 PLF-002)'),
    sprint: str = typer.Option(None, '-s', '--sprint', help='Delete all tickets in sprint (use "all" for all sprints)'),
    status: str = typer.Option(None, '--status', help='Delete tickets with this status (open|in_progress|review|done|blocked)'),
    label: list[str] = typer.Option(None, '-l', '--label', help='Delete tickets with these labels'),
    source: str = typer.Option(None, '--source', help='Delete tickets from this source tool'),
    files: list[str] = typer.Option(None, '--files', help='Delete tickets associated with files matching glob pattern(s)'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Preview what would be deleted without deleting'),
    force: bool = typer.Option(False, '-f', '--force', help='Skip confirmation prompt'),
    sync: bool = typer.Option(False, '--sync', help='Auto-sync to configured integrations after deletion'),
    sync_dry_run: bool = typer.Option(False, '--sync-dry-run', help='Preview sync without making changes'),
) -> None:
    """Delete tickets by ID(s) or filters (status, sprint, label, source, files)."""
    from planfile import Planfile
    pf = Planfile.auto_discover()

    to_delete = _collect_delete_ids(pf, ticket_ids, sprint, status, label, source, files)
    if not to_delete:
        console.print('[yellow]⚠[/yellow] No tickets match the specified criteria.')
        raise typer.Exit(0)

    deleted, not_found = _confirm_and_delete(pf, to_delete, dry_run, force)

    if deleted:
        console.print(f'[green]✓[/green] Deleted {len(deleted)} ticket(s): {", ".join(deleted)}')
    if not_found:
        console.print(f'[yellow]⚠[/yellow] {len(not_found)} ticket(s) not found: {", ".join(not_found)}')

    if sync and deleted:
        _auto_sync(str(pf.store.project_dir), None, sync_dry_run)

def _print_bulk_update_preview(
    tickets: list,
    new_status: str | None,
    new_priority: str | None,
    add_label: list[str] | None,
    remove_label: list[str] | None,
    move_to_sprint: str | None,
) -> None:
    console.print(f'[bold]Tickets to update:[/bold] ({len(tickets)} total)')
    for t in tickets:
        console.print(f'  - {t.id}: {t.name}')
    console.print('\n[bold]Updates to apply:[/bold]')
    if new_status:
        console.print(f'  status: {new_status}')
    if new_priority:
        console.print(f'  priority: {new_priority}')
    if add_label:
        console.print(f'  add labels: {", ".join(add_label)}')
    if remove_label:
        console.print(f'  remove labels: {", ".join(remove_label)}')
    if move_to_sprint:
        console.print(f'  move to sprint: {move_to_sprint}')


def _apply_label_changes(
    ticket: Any,
    base_updates: dict,
    add_label: list[str] | None,
    remove_label: list[str] | None,
) -> dict:
    updates = dict(base_updates)
    if add_label or remove_label:
        current_labels = set(ticket.labels or [])
        if add_label:
            current_labels.update(add_label)
        if remove_label:
            current_labels.difference_update(remove_label)
        updates['labels'] = list(current_labels)
    return updates


def _execute_bulk_updates(
    pf: Any,
    tickets: list,
    base_updates: dict,
    add_label: list[str] | None,
    remove_label: list[str] | None,
    move_to_sprint: str | None,
) -> tuple[list[str], list[tuple[str, str]]]:
    updated: list[str] = []
    failed: list[tuple[str, str]] = []
    for t in tickets:
        try:
            ticket_updates = _apply_label_changes(t, base_updates, add_label, remove_label)
            pf.update_ticket(t.id, **ticket_updates)
            if move_to_sprint:
                pf.store.move_ticket(t.id, move_to_sprint)
            updated.append(t.id)
        except Exception as e:
            failed.append((t.id, str(e)))
    return updated, failed


def ticket_bulk_update(
    sprint: str = typer.Option(None, '-s', '--sprint', help='Update tickets in sprint (use "all" for all sprints)'),
    status_filter: str = typer.Option(None, '--status-filter', help='Filter by current status (open|in_progress|review|done|blocked)'),
    label: list[str] = typer.Option(None, '-l', '--label', help='Filter by labels'),
    source: str = typer.Option(None, '--source', help='Filter by source tool'),
    files: list[str] = typer.Option(None, '--files', help='Filter by file glob pattern(s)'),
    # Update parameters
    new_status: str = typer.Option(None, '--new-status', help='Set new status'),
    new_priority: str = typer.Option(None, '--new-priority', help='Set new priority (critical|high|normal|low)'),
    add_label: list[str] = typer.Option(None, '--add-label', help='Add label(s)'),
    remove_label: list[str] = typer.Option(None, '--remove-label', help='Remove label(s)'),
    move_to_sprint: str = typer.Option(None, '--move-to-sprint', help='Move tickets to another sprint'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Preview what would be updated without updating'),
    force: bool = typer.Option(False, '-f', '--force', help='Skip confirmation prompt'),
    sync: bool = typer.Option(False, '--sync', help='Auto-sync to configured integrations after update'),
    sync_dry_run: bool = typer.Option(False, '--sync-dry-run', help='Preview sync without making changes'),
) -> None:
    """Bulk update tickets matching filters. Update status, priority, labels, or sprint."""
    from planfile import Planfile
    pf = Planfile.auto_discover()

    filters: dict = {}
    if status_filter:
        filters['status'] = status_filter
    if source:
        filters['source'] = source
    if label:
        filters['labels'] = list(label)
    if files:
        filters['files'] = files

    sprint_arg = sprint if sprint else 'all'
    tickets = pf.list_tickets(sprint=sprint_arg, **filters)

    if not tickets:
        console.print('[yellow]⚠[/yellow] No tickets match the specified criteria.')
        raise typer.Exit(0)

    base_updates: dict = {}
    if new_status:
        base_updates['status'] = new_status
    if new_priority:
        base_updates['priority'] = new_priority

    if not base_updates and not add_label and not remove_label and not move_to_sprint:
        console.print('[yellow]⚠[/yellow] No updates specified. Use --new-status, --new-priority, --add-label, --remove-label, or --move-to-sprint.')
        raise typer.Exit(1)

    _print_bulk_update_preview(tickets, new_status, new_priority, add_label, remove_label, move_to_sprint)

    if dry_run:
        console.print('\n[cyan]--dry-run[/cyan]: No tickets were updated.')
        raise typer.Exit(0)

    if not force:
        if not typer.confirm(f'\nUpdate {len(tickets)} ticket(s)?'):
            console.print('[dim]Cancelled.[/dim]')
            raise typer.Exit(0)

    updated, failed = _execute_bulk_updates(pf, tickets, base_updates, add_label, remove_label, move_to_sprint)

    if updated:
        console.print(f'[green]✓[/green] Updated {len(updated)} ticket(s): {", ".join(updated)}')
    if failed:
        console.print(f'[red]✗[/red] Failed to update {len(failed)} ticket(s):')
        for tid, err in failed:
            console.print(f'  - {tid}: {err}')

    if sync and updated:
        _auto_sync(str(pf.store.project_dir), None, sync_dry_run)