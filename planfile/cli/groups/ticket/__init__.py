"""Ticket command group for planfile CLI."""

import typer

from planfile.cli.core import console
from planfile.cli.groups.ticket.commands import (
    ticket_block,
    ticket_claim,
    ticket_bulk_update,
    ticket_complete,
    ticket_create,
    ticket_coverage,
    ticket_decompose,
    ticket_delete,
    ticket_depend,
    ticket_done,
    ticket_duplicates,
    ticket_fail,
    ticket_group,
    ticket_import,
    ticket_input,
    ticket_list,
    ticket_merge,
    ticket_move,
    ticket_prune_deps,
    ticket_next,
    ticket_ready,
    ticket_show,
    ticket_split,
    ticket_start,
    ticket_tree,
    ticket_update,
    ticket_validate,
)


def register_ticket_commands(app: typer.Typer) -> None:
    """Register ticket subcommands on the typer app."""
    ticket_app = typer.Typer(help="Manage tickets", invoke_without_command=True)

    @ticket_app.callback(invoke_without_command=True)
    def ticket_callback(ctx: typer.Context) -> None:
        """Manage tickets."""
        if ctx.invoked_subcommand is None:
            console.print(ctx.get_help())
            raise typer.Exit()

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
    # Git-like decomposition: split into subtasks, inspect the tree, group, and refactor-merge.
    ticket_app.command("split")(ticket_split)
    ticket_app.command("tree")(ticket_tree)
    ticket_app.command("group")(ticket_group)
    ticket_app.command("merge")(ticket_merge)
    ticket_app.command("depend")(ticket_depend)
    # Semantic layer: duplicate detection, LLM/heuristic decomposition, objective coverage.
    ticket_app.command("duplicates")(ticket_duplicates)
    ticket_app.command("decompose")(ticket_decompose)
    ticket_app.command("coverage")(ticket_coverage)
    ticket_app.command("prune-deps")(ticket_prune_deps)

    app.add_typer(ticket_app, name="ticket")
