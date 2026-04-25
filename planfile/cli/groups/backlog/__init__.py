"""Backlog management CLI commands."""

import typer

from planfile.cli.groups.backlog.commands import (
    backlog_delete,
    backlog_list,
)


def register_backlog_commands(app: typer.Typer) -> None:
    """Register backlog subcommands on the typer app."""
    backlog_app = typer.Typer(help="Manage backlog items in planfile.yaml")

    backlog_app.command("list")(backlog_list)
    backlog_app.command("delete")(backlog_delete)

    app.add_typer(backlog_app, name="backlog")
