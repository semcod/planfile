"""Backlog management CLI commands."""
import fnmatch
from pathlib import Path
import typer
import yaml
from planfile.cli.core import console

app = typer.Typer(help="Manage backlog items in planfile.yaml")

def _get_planfile_yaml_path() -> Path:
    """Find planfile.yaml in current directory or parent directories."""
    path = Path.cwd().resolve()
    while path != path.parent:
        planfile_path = path / "planfile.yaml"
        if planfile_path.exists():
            return planfile_path
        path = path.parent
    return Path.cwd() / "planfile.yaml"

def _load_planfile_yaml() -> dict:
    """Load planfile.yaml content."""
    planfile_path = _get_planfile_yaml_path()
    if not planfile_path.exists():
        console.print(f'[red]✗[/red] planfile.yaml not found at {planfile_path}')
        raise typer.Exit(1)
    with open(planfile_path) as f:
        return yaml.safe_load(f)

def _save_planfile_yaml(data: dict) -> None:
    """Save planfile.yaml content."""
    planfile_path = _get_planfile_yaml_path()
    with open(planfile_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

def _matches_files(item: dict, patterns: list[str]) -> bool:
    """Check if backlog item matches any of the file patterns."""
    files = item.get('files', [])
    if not files:
        return False
    for f in files:
        for pattern in patterns:
            if fnmatch.fnmatch(f, pattern):
                return True
    return False

def backlog_list(
    files: list[str] = typer.Option(None, '--files', help='Filter by file glob pattern(s)'),
    rule_id: str = typer.Option(None, '--rule-id', help='Filter by rule ID'),
    fmt: str = typer.Option('table', '--format', help='table | json | yaml')
) -> None:
    """List backlog items from planfile.yaml with optional filters."""
    data = _load_planfile_yaml()
    backlog = data.get('backlog', [])
    
    # Apply filters
    filtered = backlog
    if files:
        filtered = [item for item in filtered if _matches_files(item, files)]
    if rule_id:
        filtered = [item for item in filtered if item.get('rule_id') == rule_id]
    
    if fmt == 'json':
        import json
        console.print(json.dumps(filtered, indent=2, default=str))
    elif fmt == 'yaml':
        console.print(yaml.dump(filtered, default_flow_style=False, sort_keys=False))
    else:
        if not filtered:
            console.print('[dim]No backlog items found.[/dim]')
            return
        
        table = create_backlog_table(filtered)
        console.print(table)

def create_backlog_table(items):
    """Create a Rich table for displaying backlog items."""
    from rich.table import Table
    table = Table(title=f'Backlog Items ({len(items)})')
    table.add_column('ID', style='cyan', no_wrap=True)
    table.add_column('Name', style='bold')
    table.add_column('Rule ID', style='dim')
    table.add_column('Files', style='dim')
    table.add_column('Priority', style='yellow')
    
    for item in items:
        files_str = ', '.join(item.get('files', [])[:2])
        if len(item.get('files', [])) > 2:
            files_str += '...'
        table.add_row(
            item.get('id', ''),
            item.get('name', ''),
            item.get('rule_id', ''),
            files_str,
            item.get('priority', '')
        )
    return table

def _collect_backlog_to_delete(
    backlog: list, files: list[str] | None, rule_id: str | None
) -> list[tuple[str, int, dict]]:
    to_delete = []
    for i, item in enumerate(backlog):
        if files and _matches_files(item, files):
            to_delete.append(('backlog', i, item))
        elif rule_id and item.get('rule_id') == rule_id:
            to_delete.append(('backlog', i, item))
    return to_delete


def _collect_targets_to_delete(
    data: dict, files: list[str] | None
) -> list[tuple[str, dict]]:
    targets_to_delete = []
    for phase_name, phase_data in data.get('targets', {}).items():
        if isinstance(phase_data, dict) and _matches_files(phase_data, files):
            targets_to_delete.append((phase_name, phase_data))
    return targets_to_delete


def _print_deletion_preview(
    to_delete: list, targets_to_delete: list
) -> None:
    if to_delete:
        console.print(f'[bold]Backlog items to delete:[/bold] ({len(to_delete)} total)')
        for _section, _idx, item in to_delete:
            console.print(f'  - {item.get("id", "")}: {item.get("name", "")}')
    if targets_to_delete:
        console.print(f'[bold]Targets entries to delete:[/bold] ({len(targets_to_delete)} total)')
        for phase_name, _phase_data in targets_to_delete:
            console.print(f'  - targets.{phase_name}')


def _execute_backlog_deletion(data: dict, to_delete: list) -> None:
    backlog = data.get('backlog', [])
    for _section, idx, _ in sorted(to_delete, key=lambda x: x[1], reverse=True):
        del backlog[idx]
    data['backlog'] = backlog


_TARGET_FIELDS_TO_STRIP = ('files', 'rule_id', 'count', 'model_hints', 'task_type', 'priority', 'estimate')


def _execute_targets_deletion(data: dict, targets_to_delete: list) -> None:
    targets_section = data.get('targets', {})
    for phase_name, _ in targets_to_delete:
        if phase_name not in targets_section:
            continue
        for field in _TARGET_FIELDS_TO_STRIP:
            targets_section[phase_name].pop(field, None)
    data['targets'] = targets_section


def backlog_delete(
    files: list[str] = typer.Option(None, '--files', help='Delete backlog items matching file glob pattern(s)'),
    rule_id: str = typer.Option(None, '--rule-id', help='Delete backlog items with this rule ID'),
    targets: bool = typer.Option(False, '--targets', help='Also delete matching entries from targets section'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Preview what would be deleted without deleting'),
    force: bool = typer.Option(False, '-f', '--force', help='Skip confirmation prompt'),
) -> None:
    """Delete backlog items from planfile.yaml by filters (files, rule_id)."""
    data = _load_planfile_yaml()
    backlog = data.get('backlog', [])

    if not backlog and not targets:
        console.print('[yellow]⚠[/yellow] No backlog items found.')
        raise typer.Exit(0)

    to_delete = _collect_backlog_to_delete(backlog, files, rule_id)
    targets_to_delete = _collect_targets_to_delete(data, files) if targets else []

    if not to_delete and not targets_to_delete:
        console.print('[yellow]⚠[/yellow] No items match the specified criteria.')
        raise typer.Exit(0)

    _print_deletion_preview(to_delete, targets_to_delete)

    if dry_run:
        console.print('[cyan]--dry-run[/cyan]: No items were deleted.')
        raise typer.Exit(0)

    if not force:
        total_items = len(to_delete) + len(targets_to_delete)
        confirm = typer.confirm(f'Delete {total_items} item(s)?')
        if not confirm:
            console.print('[dim]Cancelled.[/dim]')
            raise typer.Exit(0)

    if to_delete:
        _execute_backlog_deletion(data, to_delete)
    if targets_to_delete:
        _execute_targets_deletion(data, targets_to_delete)

    _save_planfile_yaml(data)
    console.print(f'[green]✓[/green] Deleted {len(to_delete) + len(targets_to_delete)} item(s)')
