import logging

import typer
from rich.console import Console

from planfile.cli import auto_loop
from planfile.cli.cmd.cmd_apply import (
    apply_strategy_cli,
)
from planfile.cli.cmd.cmd_generate import generate_from_files_cmd, generate_strategy_cli
from planfile.cli.cmd.cmd_init import init_strategy_cli
from planfile.cli.cmd.cmd_review import review_strategy_cli

# Import all extracted functions to maintain API compatibility
from planfile.cli.cmd.cmd_validate import validate_strategy_cli

app = typer.Typer(help="planfile — universal ticket standard for developer toolchains")
console = Console()
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

# Add auto subcommand
app.add_typer(auto_loop.app, name="auto", help="Automated CI/CD commands")

# Register split commands (replaces old add_extra_commands from extra_commands.py)
from planfile.cli.cmd.cmd_compare import register_compare_commands
from planfile.cli.cmd.cmd_export import register_export_commands
from planfile.cli.cmd.cmd_stats import register_stats_commands
from planfile.cli.cmd.cmd_template import register_template_commands
from planfile.cli.cmd.cmd_ticket import register_ticket_commands

register_export_commands(app)
register_compare_commands(app)
register_template_commands(app)
register_stats_commands(app)
register_ticket_commands(app)

# Health + examples (remaining from extra_commands.py)
from planfile.cli.extra_commands import add_extra_commands

add_extra_commands(app)

# Register command decorators
app.command("apply")(apply_strategy_cli)
app.command("review")(review_strategy_cli)
app.command("validate")(validate_strategy_cli)
app.command("generate")(generate_strategy_cli)
app.command("generate-from-files")(generate_from_files_cmd)
app.command("init")(init_strategy_cli)


def main() -> None:
    """Main CLI entry point."""
    app()
