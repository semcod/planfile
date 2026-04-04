"""Ticket command group for planfile CLI."""

import typer

from planfile.cli.groups.ticket.commands import (
    ticket_block,
    ticket_create,
    ticket_done,
    ticket_export_todo,
    ticket_import,
    ticket_import_todo,
    ticket_list,
    ticket_move,
    ticket_review,
    ticket_show,
    ticket_start,
    ticket_update,
)


def register_ticket_commands(app: typer.Typer) -> None:
    """Register ticket subcommands on the typer app."""
    ticket_app = typer.Typer(help="Manage tickets")

    ticket_app.command("create")(ticket_create)
    ticket_app.command("list")(ticket_list)
    ticket_app.command("show")(ticket_show)
    ticket_app.command("update")(ticket_update)
    ticket_app.command("move")(ticket_move)
    ticket_app.command("import")(ticket_import)
    ticket_app.command("done")(ticket_done)
    ticket_app.command("start")(ticket_start)
    ticket_app.command("block")(ticket_block)
    ticket_app.command("review")(ticket_review)
    ticket_app.command("import-todo")(ticket_import_todo)
    ticket_app.command("export-todo")(ticket_export_todo)

    app.add_typer(ticket_app, name="ticket")
