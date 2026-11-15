"""
Additional CLI commands for planfile.

This module registers additional command groups to the main CLI app.
Commands are organized into separate modules for better maintainability.
"""

import typer

from planfile.cli.groups.examples import create_examples_app
from planfile.cli.groups.health import create_health_app
from planfile.cli.groups.ticket.reconcile import (
    ticket_executable_queue,
    ticket_reconcile,
)


def add_extra_commands(app: typer.Typer) -> None:
    """Add health, examples, reconciliation, and executable-queue commands to the CLI app."""
    # Add health commands
    health_app = create_health_app()
    app.add_typer(health_app, name="health")

    # Add examples commands
    examples_app = create_examples_app()
    app.add_typer(examples_app, name="examples")

    # Top-level reconciliation and canonical executable queue commands
    app.command("reconcile")(ticket_reconcile)
    app.command("executable-queue")(ticket_executable_queue)
