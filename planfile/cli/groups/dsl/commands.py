"""planfile dsl — interactive DSL shell and single-command execution."""

from __future__ import annotations

import json
import sys

import typer
import yaml

from planfile.cli.core import console


def dsl_run(
    command: str | None = typer.Argument(None, help="DSL command to execute. Omit for interactive shell."),
    project: str = typer.Option(".", "--project", "-p", help="Project root directory"),
    fmt: str = typer.Option("text", "--format", "-f", help="Output format: text | json | yaml"),
    fail_on_error: bool = typer.Option(False, "--fail-on-error", help="Exit with code 1 if command fails"),
) -> None:
    """Execute a DSL / natural language command or start an interactive shell.

    Examples:
      planfile dsl "list tickets sprint=current"
      planfile dsl "create ticket 'Fix login bug' priority=high"
      planfile dsl "done ticket PLF-001"
      planfile dsl "validate"
      planfile dsl          # interactive shell
    """
    from planfile.dsl import DSLExecutor
    executor = DSLExecutor(project_path=project)

    if command:
        _run_single(executor, command, fmt, fail_on_error)
    else:
        _interactive_shell(executor, fmt)


def _run_single(executor, command: str, fmt: str, fail_on_error: bool) -> None:
    result = executor.run(command)

    if fmt == "json":
        print(json.dumps(result.to_dict(), indent=2, default=str))
    elif fmt == "yaml":
        console.print(yaml.dump(result.to_dict(), default_flow_style=False, sort_keys=False, allow_unicode=True))
    else:
        if result.ok:
            if result.message:
                console.print(f"[green]✓[/green] {result.message}")
            if result.data is not None:
                _pretty_data(result.data)
        else:
            console.print(f"[red]✗[/red] {result.error}")

    if fail_on_error and not result.ok:
        raise typer.Exit(1)


def _pretty_data(data) -> None:
    """Print structured data in a human-readable way."""
    if isinstance(data, list):
        if not data:
            console.print("[dim]  (empty)[/dim]")
            return
        if isinstance(data[0], dict):
            from rich.table import Table
            keys = list(data[0].keys())
            table = Table()
            for k in keys:
                table.add_column(k, style="cyan" if k in ("id", "ticket_id") else None)
            for row in data:
                table.add_row(*[str(row.get(k, "")) for k in keys])
            console.print(table)
        else:
            for item in data:
                console.print(f"  • {item}")
    elif isinstance(data, dict):
        for k, v in data.items():
            console.print(f"  [bold]{k}[/bold]: {v}")
    elif isinstance(data, str) and len(data) > 80:
        console.print(data)
    else:
        console.print(str(data))


def _interactive_shell(executor, fmt: str) -> None:
    """Run an interactive DSL REPL."""
    console.print("[bold cyan]planfile DSL shell[/bold cyan]  [dim](type 'help' for commands, 'exit' to quit)[/dim]")

    try:
        import readline  # noqa: F401 — enables history on Linux/macOS
    except ImportError:
        pass

    while True:
        try:
            line = input("[dim]planfile>[/dim] " if sys.stdin.isatty() else "")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/dim]")
            break

        line = line.strip()
        if not line:
            continue
        if line.lower() in ("exit", "quit", "q", ":q"):
            console.print("[dim]Bye.[/dim]")
            break

        _run_single(executor, line, fmt, fail_on_error=False)


def register_dsl_commands(app: typer.Typer) -> None:
    """Register DSL commands on the main app."""
    dsl_app = typer.Typer(
        help="Execute DSL / natural language commands against planfile.",
        context_settings={"help_option_names": ["-h", "--help"]},
    )
    dsl_app.command("run", help="Run a DSL command or start interactive shell.")(dsl_run)

    @dsl_app.command("help")
    def dsl_help_cmd() -> None:
        """Show DSL command reference."""
        from planfile.dsl import DSLCommand, DSLExecutor
        executor = DSLExecutor()
        result = executor.execute(DSLCommand(verb="help"))
        console.print(result.message or "")

    app.add_typer(dsl_app, name="dsl", help="DSL / natural language commands")
