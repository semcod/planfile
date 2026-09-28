"""Planfile CLI commands."""

import logging
import os
import sys

import typer

from planfile.cli.core import console

logger = logging.getLogger(__name__)

def version_callback(value: bool) -> None:
    if value:
        import planfile
        console.print(f"Planfile CLI version: {planfile.__version__}")
        raise typer.Exit()


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


def _build_app(*, ticket_only: bool = False) -> typer.Typer:
    """Keep ticket subprocesses from constructing unrelated command trees."""
    from planfile.cli.groups.ticket import register_ticket_commands

    app = typer.Typer(
        help="planfile — universal ticket standard for developer toolchains",
        invoke_without_command=True,
    )
    app.callback()(main_callback)
    if ticket_only:
        register_ticket_commands(app)
        return app

    from planfile.cli.extra_commands import add_extra_commands
    from planfile.cli.groups.apply import register_apply_commands
    from planfile.cli.groups.auto import register_auto_commands
    from planfile.cli.groups.backlog import register_backlog_commands
    from planfile.cli.groups.config import register_config_commands
    from planfile.cli.groups.dsl import register_dsl_commands
    from planfile.cli.groups.generate import register_generate_commands
    from planfile.cli.groups.info import register_info_commands
    from planfile.cli.groups.init import register_init_commands
    from planfile.cli.groups.query import register_query_commands
    from planfile.cli.groups.review import register_review_commands
    from planfile.cli.groups.serve import register_serve_commands
    from planfile.cli.groups.storage import register_storage_commands
    from planfile.cli.groups.sync import register_sync_commands
    from planfile.cli.groups.validate import register_validate_commands

    register_apply_commands(app)
    register_auto_commands(app)
    register_dsl_commands(app)
    register_config_commands(app)
    register_backlog_commands(app)
    register_generate_commands(app)
    register_init_commands(app)
    register_query_commands(app)
    register_review_commands(app)
    register_serve_commands(app)
    register_storage_commands(app)
    register_sync_commands(app)
    register_ticket_commands(app)
    register_validate_commands(app)
    register_info_commands(app)
    add_extra_commands(app)
    return app


def __getattr__(name: str):
    """Preserve the complete public app for embedded callers and CliRunner."""
    if name == "app":
        app = _build_app()
        globals()[name] = app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    """Main CLI entry point."""
    # Options before the command and completion requests use the full parser.
    # Do not guess which positional token belongs to an unknown root option.
    ticket_only = sys.argv[1:2] == ["ticket"] and not any(
        key.endswith("_COMPLETE") and value for key, value in os.environ.items()
    )
    _build_app(ticket_only=ticket_only)()
