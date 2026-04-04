"""
Additional CLI commands for planfile.

This module registers additional command groups to the main CLI app.
Commands are organized into separate modules for better maintainability.
"""

from planfile.cli.cmd.cmd_examples import create_examples_app
from planfile.cli.cmd.cmd_health import create_health_app


def add_extra_commands(app):
    """Add health and examples command groups to the CLI app."""
    # Add health commands
    health_app = create_health_app()
    app.add_typer(health_app, name="health")

    # Add examples commands
    examples_app = create_examples_app()
    app.add_typer(examples_app, name="examples")
