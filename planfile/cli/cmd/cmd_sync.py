"""Sync commands for planfile integrations.

NOTE: This module is now a thin shim. The actual implementation has been moved to:
    planfile.cli.groups.sync

Import from the new location for new code. This module is kept for backward compatibility.
"""

# Re-export everything from the new location for backward compatibility
from planfile.cli.groups.sync.commands import all_cmd as all
from planfile.cli.groups.sync.commands import github_cmd as github
from planfile.cli.groups.sync.commands import gitlab_cmd as gitlab
from planfile.cli.groups.sync.commands import jira_cmd as jira
from planfile.cli.groups.sync.commands import markdown_cmd as markdown
from planfile.cli.groups.sync.core import sync_integration
from planfile.cli.groups.sync.core import (
    _collect_tickets_from_backlog,
    _collect_tickets_from_sprint,
    _execute_sync_with_progress,
    _initialize_backend,
    _load_tickets_for_sync,
    _load_tickets_v1_format,
    _ticket_matches_integration,
)

# Legacy console import (now in core)
from planfile.cli.core import console

# Legacy imports that other modules might depend on
from planfile.integrations.config import IntegrationConfig
from planfile.sync.operations import sync_from_external, sync_to_external
from planfile.sync.state import SyncState
from planfile.sync.utils import save_v1_format as _save_v1_format

import typer

# Create the legacy sync_app (for backward compatibility)
sync_app = typer.Typer(help="Sync tickets with external systems")


@sync_app.command()
def github_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with GitHub Issues."""
    sync_integration("github", directory, dry_run, direction)


@sync_app.command()
def gitlab_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with GitLab Issues."""
    sync_integration("gitlab", directory, dry_run, direction)


@sync_app.command()
def jira_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with Jira."""
    sync_integration("jira", directory, dry_run, direction)


@sync_app.command()
def markdown_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with markdown files (CHANGELOG.md, TODO.md)."""
    sync_integration("markdown", directory, dry_run, direction)


@sync_app.command()
def all_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with all configured integrations."""
    from planfile.cli.groups.sync.commands import all_cmd as new_all_cmd
    new_all_cmd(directory, dry_run, direction)


def create_sync_app() -> typer.Typer:
    """Create the sync command app."""
    return sync_app


# Legacy helper functions that might be imported by other modules
def find_planfile_ticket(external_ticket, store, sync_state) -> str | None:
    """Find corresponding planfile ticket for external ticket using sync state."""
    ext_id = str(external_ticket.get('id', ''))

    # First check sync state
    local_id = sync_state.get_local_id(ext_id)
    if local_id:
        return local_id

    # Fallback: search by external_id in tickets
    ext_id_int = ext_id.lstrip('#')

    # Check sprint
    sprint = store.load_sprint("current")
    if sprint:
        for ticket_id, ticket in sprint.get("tickets", {}).items():
            if ticket.get("external_id") == ext_id or ticket.get("external_id") == ext_id_int:
                return ticket_id

    # Check backlog
    backlog = store.load_backlog()
    if backlog:
        for ticket_id, ticket in backlog.get("tickets", {}).items():
            if ticket.get("external_id") == ext_id or ticket.get("external_id") == ext_id_int:
                return ticket_id

    return None


def _save_v1_format_legacy(file_path: str, data: dict) -> None:
    """Save data back to v1 format YAML file."""
    import yaml
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


__all__ = [
    # Main function
    'sync_integration',
    # Legacy command handlers
    'github', 'gitlab', 'jira', 'markdown', 'all',
    'github_cmd', 'gitlab_cmd', 'jira_cmd', 'markdown_cmd', 'all_cmd',
    # Legacy app
    'sync_app', 'create_sync_app',
    # Helper functions
    'find_planfile_ticket',
    '_save_v1_format_legacy',
    # Internal helpers (for tests/other modules that import them)
    '_initialize_backend',
    '_ticket_matches_integration',
    '_collect_tickets_from_sprint',
    '_collect_tickets_from_backlog',
    '_load_tickets_v1_format',
    '_load_tickets_for_sync',
    '_execute_sync_with_progress',
    # Legacy imports
    'console',
    'IntegrationConfig',
    'SyncState',
    'sync_from_external',
    'sync_to_external',
    '_save_v1_format',
]
