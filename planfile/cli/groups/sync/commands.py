"""Sync command handlers for planfile CLI."""

from __future__ import annotations

import os
import time
from pathlib import Path

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


def handle_no_integrations(
    directory: str,
    dry_run: bool,
    direction: str
) -> None:
    """Handle syncing when no integrations are configured by falling back to markdown."""
    console.print("[yellow]⚠️ No integrations configured, using default markdown backend[/yellow]")
    sync_integration("markdown", directory, dry_run, direction)


def sync_all_integrations(
    integrations: list[str],
    directory: str,
    dry_run: bool,
    direction: str
) -> None:
    """Sync with all configured integrations, handling errors per integration."""
    console.print(f"🔄 Syncing with integrations: {', '.join(integrations)}")

    for integration in integrations:
        console.print(f"\n📡 Syncing with {integration}...")
        try:
            sync_integration(integration, directory, dry_run, direction, show_header=False)
        except Exception as e:
            console.print(f"[red]❌ Failed to sync with {integration}: {e}[/red]")


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
        handle_no_integrations(directory, dry_run, direction)
        return

    integrations = list(config.config.get("integrations", {}).keys())

    sync_all_integrations(integrations, directory, dry_run, direction)


def watch_cmd(
    directory: str = typer.Argument(".", help="Directory to watch"),
    interval: int = typer.Option(5, "--interval", "-i", help="Polling interval in seconds"),
    integrations: list[str] = typer.Option(None, "--integration", help="Specific integrations to watch (default: all configured)"),
    direction: str = typer.Option("to", "--direction", help="Sync direction: to, from, or both"),
    once: bool = typer.Option(False, "--once", help="Run sync once and exit (no watch loop)"),
) -> None:
    """Watch .planfile/ directory and auto-sync on changes."""
    from planfile.integrations.config import IntegrationConfig

    planfile_dir = Path(directory) / ".planfile"
    if not planfile_dir.exists():
        console.print(f"[red]❌ No .planfile/ directory found in {directory}[/red]")
        raise typer.Exit(1)

    config = IntegrationConfig(directory)
    config.load_configs()

    if integrations:
        to_sync = integrations
    else:
        to_sync = list(config.config.get("integrations", {}).keys())
        if "markdown" not in to_sync:
            to_sync.append("markdown")

    if not to_sync:
        to_sync = ["markdown"]

    console.print(f"[blue]👁️ Watching {planfile_dir} for changes...[/blue]")
    console.print(f"[dim]   Sync targets: {', '.join(to_sync)}[/dim]")
    console.print(f"[dim]   Polling interval: {interval}s[/dim]")
    console.print(f"[dim]   Direction: {direction}[/dim]")
    console.print("[dim]   Press Ctrl+C to stop[/dim]\n")

    def get_file_states() -> dict[str, float]:
        states = {}
        for path in planfile_dir.rglob("*.yaml"):
            try:
                states[str(path)] = path.stat().st_mtime
            except OSError:
                pass
        return states

    last_states = get_file_states()

    if once:
        console.print("[blue]🔄 Running one-time sync...[/blue]")
        for integration in to_sync:
            try:
                sync_integration(integration, directory, False, direction, show_header=False)
            except Exception as e:
                console.print(f"[yellow]⚠️ Sync failed for {integration}: {e}[/yellow]")
        return

    try:
        while True:
            time.sleep(interval)
            current_states = get_file_states()

            changed = False
            for path, mtime in current_states.items():
                if path not in last_states or last_states[path] != mtime:
                    changed = True
                    break

            if not changed:
                for path in last_states:
                    if path not in current_states:
                        changed = True
                        break

            if changed:
                console.print(f"[blue]📝 Detected changes at {time.strftime('%H:%M:%S')}[/blue]")
                for integration in to_sync:
                    try:
                        sync_integration(integration, directory, False, direction, show_header=False)
                    except Exception as e:
                        console.print(f"[yellow]⚠️ Sync failed for {integration}: {e}[/yellow]")
                console.print("")
                last_states = current_states

    except KeyboardInterrupt:
        console.print("\n[dim]👋 Watch stopped.[/dim]")
