"""Planfile CLI commands."""

import logging

import typer

from planfile.cli.core import console
from planfile.cli.groups.sync import register_sync_commands
from planfile.cli.groups.ticket import register_ticket_commands
from planfile.cli.groups.generate import register_generate_commands
from planfile.cli.groups.init import register_init_commands
from planfile.cli.groups.review import register_review_commands
from planfile.cli.groups.auto import register_auto_commands

# Legacy imports for remaining commands
from planfile.cli.cmd.cmd_apply import apply_strategy_cli
from planfile.cli.cmd.cmd_validate import validate_strategy_cli

app = typer.Typer(help="planfile — universal ticket standard for developer toolchains")
logger = logging.getLogger(__name__)

def version_callback(value: bool) -> None:
    if value:
        import planfile
        console.print(f"Planfile CLI version: {planfile.__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool | None = typer.Option(
        None, "--version", "-v",
        help="Show CLI version and exit",
        callback=version_callback,
        is_eager=True
    )
) -> None:
    pass


# Register all command groups
register_sync_commands(app)
register_ticket_commands(app)
register_generate_commands(app)
register_init_commands(app)
register_review_commands(app)
register_auto_commands(app)

# Legacy commands that haven't been migrated yet
from planfile.cli.cmd.cmd_compare import register_compare_commands
from planfile.cli.cmd.cmd_export import register_export_commands
from planfile.cli.cmd.cmd_stats import register_stats_commands
from planfile.cli.cmd.cmd_template import register_template_commands

register_compare_commands(app)
register_export_commands(app)
register_template_commands(app)
register_stats_commands(app)

# Health + examples
from planfile.cli.extra_commands import add_extra_commands

add_extra_commands(app)

# Remaining standalone commands
app.command("apply")(apply_strategy_cli)
app.command("validate")(validate_strategy_cli)


def main() -> None:
    """Main CLI entry point."""
    app()
