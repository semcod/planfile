"""Examples command group for planfile CLI."""

import typer

from planfile.cli.groups.examples.commands import create_examples_app


def register_examples_commands(app: typer.Typer) -> None:
    """Register examples commands on the typer app."""
    examples_app = create_examples_app()
    app.add_typer(examples_app, name="examples")
