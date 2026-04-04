"""Init command group for planfile CLI."""

import typer

from planfile.cli.groups.init.commands import init_strategy_cli


def register_init_commands(app: typer.Typer) -> None:
    """Register init subcommand on the typer app."""
    app.command("init")(init_strategy_cli)
