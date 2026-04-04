"""Health command group for planfile CLI."""

import typer

from planfile.cli.groups.health.commands import create_health_app


def register_health_commands(app: typer.Typer) -> None:
    """Register health commands on the typer app."""
    health_app = create_health_app()
    app.add_typer(health_app, name="health")
