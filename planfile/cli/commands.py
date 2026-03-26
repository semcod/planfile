import typer
import logging
from rich.console import Console

from planfile.cli import auto_loop

# Import all extracted functions to maintain API compatibility
from planfile.cli.cmd.cmd_utils import (
    get_backend,
    _load_and_validate_strategy,
    _load_backend_config,
    _parse_sprint_filter,
    _select_backend
)
from planfile.cli.cmd.cmd_apply import (
    _execute_apply_strategy,
    _display_apply_results,
    _save_results,
    apply_strategy_cli
)
from planfile.cli.cmd.cmd_review import review_strategy_cli
from planfile.cli.cmd.cmd_validate import validate_strategy_cli
from planfile.cli.cmd.cmd_generate import generate_strategy_cli, generate_from_files_cmd

app = typer.Typer(help="Strategy CLI - Manage strategies and sprints")
console = Console()
logger = logging.getLogger(__name__)

# Add auto subcommand
app.add_typer(auto_loop.app, name="auto", help="Automated CI/CD commands")

# Import and add extra commands
from planfile.cli.extra_commands import add_extra_commands
add_extra_commands(app)

# Register command decorators
app.command("apply")(apply_strategy_cli)
app.command("review")(review_strategy_cli)
app.command("validate")(validate_strategy_cli)
app.command("generate")(generate_strategy_cli)
app.command("generate-from-files")(generate_from_files_cmd)

def main():
    """Main CLI entry point."""
    app()
