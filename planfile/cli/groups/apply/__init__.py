"""Apply command group for planfile CLI."""

import typer

from planfile.cli.groups.apply.commands import apply_strategy_cli


def register_apply_commands(app: typer.Typer) -> None:
    """Register apply subcommand on the typer app."""
    app.command("apply")(apply_strategy_cli)
