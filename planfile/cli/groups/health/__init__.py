"""Health command group for planfile CLI."""

import typer

from planfile.cli.core import register_typer_group
from planfile.cli.groups.health.commands import create_health_app


def register_health_commands(app: typer.Typer) -> None:
    """Register health commands on the typer app."""
    register_typer_group(app, "health", create_health_app)
