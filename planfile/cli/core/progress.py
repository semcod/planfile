"""Progress bar helpers for CLI operations."""

from typing import Callable, TypeVar

from rich.progress import Progress, SpinnerColumn, TextColumn

from planfile.cli.core.console import console

T = TypeVar('T')


def with_spinner(description: str, fn: Callable[[], T]) -> T:
    """Execute function with a spinner progress indicator."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(description, total=None)
        result = fn()
        progress.update(task, completed=True)
        return result


def create_progress() -> Progress:
    """Create a standard progress bar instance."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    )
