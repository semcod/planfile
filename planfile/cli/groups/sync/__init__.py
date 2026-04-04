"""Sync command group for planfile CLI."""

import typer

from planfile.cli.groups.sync.commands import all_cmd, github_cmd, gitlab_cmd, jira_cmd, markdown_cmd


def register_sync_commands(app: typer.Typer) -> None:
    """Register all sync commands with the main CLI app."""
    sync_app = typer.Typer(help="Sync tickets with external systems")

    sync_app.command("github")(github_cmd)
    sync_app.command("gitlab")(gitlab_cmd)
    sync_app.command("jira")(jira_cmd)
    sync_app.command("markdown")(markdown_cmd)
    sync_app.command("all")(all_cmd)

    app.add_typer(sync_app, name="sync")
