"""Sync command handlers for planfile CLI."""

from __future__ import annotations

import typer

from planfile.cli.core import console, print_success
from planfile.cli.groups.sync.core import sync_integration


def github_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with GitHub Issues."""
    sync_integration("github", directory, dry_run, direction)


def gitlab_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with GitLab Issues."""
    sync_integration("gitlab", directory, dry_run, direction)


def jira_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with Jira."""
    sync_integration("jira", directory, dry_run, direction)


def markdown_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with markdown files (CHANGELOG.md, TODO.md)."""
    sync_integration("markdown", directory, dry_run, direction)


def all_cmd(
    directory: str = typer.Argument(".", help="Directory containing planfile configs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced without doing it"),
    direction: str = typer.Option("both", "--direction", help="Sync direction: to, from, or both")
) -> None:
    """Sync tickets with all configured integrations."""
    from planfile.integrations.config import IntegrationConfig

    config = IntegrationConfig(directory)
    config.load_configs()

    # Check if any integrations are configured
    if not config.has_configured_integrations():
        console.print("[yellow]⚠️ No integrations configured, using default markdown backend[/yellow]")
        sync_integration("markdown", directory, dry_run, direction)
        return

    integrations = config.config.get("integrations", {}).keys()

    console.print(f"🔄 Syncing with integrations: {', '.join(integrations)}")

    for integration in integrations:
        console.print(f"\n📡 Syncing with {integration}...")
        try:
            sync_integration(integration, directory, dry_run, direction, show_header=False)
        except Exception as e:
            console.print(f"[red]❌ Failed to sync with {integration}: {e}[/red]")
