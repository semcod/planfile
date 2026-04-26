"""Ticket command group for planfile CLI."""

import typer

from planfile.cli.groups.ticket.commands import (
    ticket_block,
    ticket_bulk_update,
    ticket_create,
    ticket_delete,
    ticket_done,
    ticket_import,
    ticket_list,
    ticket_move,
    ticket_show,
    ticket_start,
    ticket_update,
    ticket_validate,
)


def register_ticket_commands(app: typer.Typer) -> None:
    """Register ticket subcommands on the typer app."""
    ticket_app = typer.Typer(help="Manage tickets")

    ticket_app.command("create")(ticket_create)
    ticket_app.command("list")(ticket_list)
    ticket_app.command("show")(ticket_show)
    ticket_app.command("update")(ticket_update)
    ticket_app.command("delete")(ticket_delete)
    ticket_app.command("bulk-update")(ticket_bulk_update)
    ticket_app.command("move")(ticket_move)
    ticket_app.command("import")(ticket_import)
    ticket_app.command("done")(ticket_done)
    ticket_app.command("start")(ticket_start)
    ticket_app.command("block")(ticket_block)
    ticket_app.command("validate")(ticket_validate)

    app.add_typer(ticket_app, name="ticket")
