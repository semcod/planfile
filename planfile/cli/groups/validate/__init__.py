"""Validate command group for planfile CLI."""

import typer

from planfile.cli.groups.validate.commands import validate_strategy_cli


def register_validate_commands(app: typer.Typer) -> None:
    """Register validate subcommand on the typer app."""
    app.command("validate")(validate_strategy_cli)
