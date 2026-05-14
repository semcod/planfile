"""Serve command group for planfile CLI."""

import typer

from planfile.cli.core import register_simple_command
from planfile.cli.groups.serve.commands import serve_cli


def register_serve_commands(app: typer.Typer) -> None:
    """Register serve subcommand on the typer app."""
    register_simple_command(app, "serve", serve_cli, help_text="Start the planfile REST API server")
