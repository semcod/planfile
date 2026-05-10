"""Ticket command group for planfile CLI."""

import typer

from planfile.cli.groups.ticket.commands import (
    ticket_block,
    ticket_claim,
    ticket_bulk_update,
    ticket_complete,
    ticket_create,
    ticket_delete,
    ticket_done,
    ticket_fail,
    ticket_import,
    ticket_input,
    ticket_list,
    ticket_move,
    ticket_next,
    ticket_ready,
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
    ticket_app.command("next")(ticket_next)
    ticket_app.command("claim")(ticket_claim)
    ticket_app.command("show")(ticket_show)
    ticket_app.command("update")(ticket_update)
    ticket_app.command("delete")(ticket_delete)
    ticket_app.command("bulk-update")(ticket_bulk_update)
    ticket_app.command("move")(ticket_move)
    ticket_app.command("import")(ticket_import)
    ticket_app.command("done")(ticket_done)
    ticket_app.command("complete")(ticket_complete)
    ticket_app.command("fail")(ticket_fail)
    ticket_app.command("input")(ticket_input)
    ticket_app.command("ready")(ticket_ready)
    ticket_app.command("start")(ticket_start)
    ticket_app.command("block")(ticket_block)
    ticket_app.command("validate")(ticket_validate)

    app.add_typer(ticket_app, name="ticket")
