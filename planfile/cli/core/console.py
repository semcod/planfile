"""Rich console singleton for CLI output."""

from rich.console import Console

# Shared console instance for all CLI modules
console = Console()


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓ {message}[/green]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]❌ {message}[/red]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠️ {message}[/yellow]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[cyan]ℹ️ {message}[/cyan]")


def print_dim(message: str) -> None:
    """Print a dimmed message."""
    console.print(f"[dim]{message}[/dim]")
