"""Query command group for planfile CLI."""

import typer

from planfile.cli.groups.query.commands import (
    compare_cmd,
    export_cmd,
    merge_cmd,
    stats_cmd,
)


def register_query_commands(app: typer.Typer) -> None:
    """Register all query commands with the main CLI app."""
    query_app = typer.Typer(help="Query and analyze strategies")

    query_app.command("stats")(stats_cmd)
    query_app.command("compare")(compare_cmd)
    query_app.command("export")(export_cmd)
    query_app.command("merge")(merge_cmd)

    app.add_typer(query_app, name="query")
