"""Review command group for planfile CLI."""

import typer

from planfile.cli.groups.review.commands import review_strategy_cli


def register_review_commands(app: typer.Typer) -> None:
    """Register review subcommand on the typer app."""
    app.command("review")(review_strategy_cli)
