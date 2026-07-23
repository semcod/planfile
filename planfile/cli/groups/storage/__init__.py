"""Ticket storage management commands."""

import typer

from planfile.cli.core import register_typer_group
from planfile.cli.groups.storage.commands import create_storage_app


def register_storage_commands(app: typer.Typer) -> None:
    register_typer_group(app, "storage", create_storage_app)
