"""Generate command group for planfile CLI."""

import typer

from planfile.cli.groups.generate.commands import (
    generate_from_files_cmd,
    generate_strategy_cli,
)


def register_generate_commands(app: typer.Typer) -> None:
    """Register generate subcommands on the typer app."""
    generate_app = typer.Typer(help="Generate strategy from project analysis")

    generate_app.command("strategy")(generate_strategy_cli)
    generate_app.command("from-files")(generate_from_files_cmd)

    app.add_typer(generate_app, name="generate")
