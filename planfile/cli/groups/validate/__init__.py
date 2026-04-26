"""Validate command group for planfile CLI."""

import typer

from planfile.cli.core import register_simple_command
from planfile.cli.groups.validate.commands import validate_schema_cli, validate_strategy_cli, validate_testql_cli


def register_validate_commands(app: typer.Typer) -> None:
    """Register validate subcommand on the typer app."""
    validate_app = typer.Typer(help="Validate planfile files")
    validate_app.command("strategy")(validate_strategy_cli)
    validate_app.command("schema")(validate_schema_cli)
    validate_app.command("testql")(validate_testql_cli)
    app.add_typer(validate_app, name="validate")
