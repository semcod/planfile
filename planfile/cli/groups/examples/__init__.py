"""Examples command group for planfile CLI."""

import typer

from planfile.cli.core import register_typer_group
from planfile.cli.groups.examples.commands import create_examples_app


def register_examples_commands(app: typer.Typer) -> None:
    """Register examples commands on the typer app."""
    register_typer_group(app, "examples", create_examples_app)
