"""Planfile CLI commands."""

import logging

import typer

from planfile.cli.core import console
from planfile.cli.groups.apply import register_apply_commands
from planfile.cli.groups.auto import register_auto_commands
from planfile.cli.groups.backlog import register_backlog_commands
from planfile.cli.groups.generate import register_generate_commands
from planfile.cli.groups.init import register_init_commands
from planfile.cli.groups.query import register_query_commands
from planfile.cli.groups.review import register_review_commands
from planfile.cli.groups.serve import register_serve_commands
from planfile.cli.groups.sync import register_sync_commands
from planfile.cli.groups.ticket import register_ticket_commands
from planfile.cli.groups.dsl import register_dsl_commands
from planfile.cli.groups.validate import register_validate_commands

app = typer.Typer(
    help="planfile — universal ticket standard for developer toolchains",
    invoke_without_command=True,
)
logger = logging.getLogger(__name__)

def version_callback(value: bool) -> None:
    if value:
        import planfile
        console.print(f"Planfile CLI version: {planfile.__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None, "--version", "-v",
        help="Show CLI version and exit",
        callback=version_callback,
        is_eager=True
    )
) -> None:
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


# Register all command groups
register_apply_commands(app)
register_auto_commands(app)
register_dsl_commands(app)
register_backlog_commands(app)
register_generate_commands(app)
register_init_commands(app)
register_query_commands(app)
register_review_commands(app)
register_serve_commands(app)
register_sync_commands(app)
register_ticket_commands(app)
register_validate_commands(app)

# Health + examples
from planfile.cli.extra_commands import add_extra_commands

add_extra_commands(app)


def main() -> None:
    """Main CLI entry point."""
    app()
