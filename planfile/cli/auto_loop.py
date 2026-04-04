"""Auto-loop CLI command for sprintstrat.

NOTE: This module is now a thin shim. The actual implementation has been moved to:
    planfile.cli.groups.auto

Import from the new location for new code. This module is kept for backward compatibility.
"""

# Re-export everything from the new location for backward compatibility
from planfile.cli.groups.auto import register_auto_commands
from planfile.cli.groups.auto.commands import (
    auto_loop_cmd,
    ci_status_cmd,
    get_backend,
)

# Legacy compatibility - create app with commands
import typer
app = typer.Typer(help="Automated CI/CD commands")
app.command("auto-loop")(auto_loop_cmd)
app.command("ci-status")(ci_status_cmd)


def create_auto_app() -> typer.Typer:
    """Create the auto command app (legacy compatibility)."""
    return app
