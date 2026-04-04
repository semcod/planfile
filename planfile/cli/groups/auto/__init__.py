"""Auto command group for planfile CLI."""

import typer

from planfile.cli.groups.auto.commands import (
    auto_loop_cmd,
    ci_status_cmd,
)


def register_auto_commands(app: typer.Typer) -> None:
    """Register auto subcommands on the typer app."""
    auto_app = typer.Typer(help="Automated CI/CD commands")

    auto_app.command("auto-loop")(auto_loop_cmd)
    auto_app.command("ci-status")(ci_status_cmd)

    app.add_typer(auto_app, name="auto")
