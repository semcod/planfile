"""Common error handling for CLI commands."""

import typer

from planfile.cli.core.console import console, print_error


def exit_with_error(message: str, code: int = 1) -> None:
    """Print error message and exit with code."""
    print_error(message)
    raise typer.Exit(code)


def exit_with_warning(message: str, code: int = 0) -> None:
    """Print warning message and exit with code."""
    console.print(f"[yellow]⚠️ {message}[/yellow]")
    raise typer.Exit(code)


def handle_exception(e: Exception, context: str = "") -> None:
    """Handle exception with optional context."""
    msg = f"{context}: {e}" if context else str(e)
    print_error(msg)
    raise typer.Exit(1)
