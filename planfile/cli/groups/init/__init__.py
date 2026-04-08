"""Init command group for planfile CLI."""

import typer

from planfile.cli.core import register_simple_command
from planfile.cli.groups.init.commands import init_strategy_cli


def register_init_commands(app: typer.Typer) -> None:
    """Register init subcommand on the typer app."""
    register_simple_command(app, "init", init_strategy_cli)
