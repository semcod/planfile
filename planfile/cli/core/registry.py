"""Command registry for organizing CLI commands."""

from typing import Callable

import typer

# Type alias for command registration functions
CommandRegistrar = Callable[[typer.Typer], None]


def register_simple_command(
    app: typer.Typer,
    name: str,
    command: Callable,
    help_text: str | None = None,
) -> None:
    """Register a simple single command on the typer app.

    Args:
        app: The main typer app
        name: Command name
        command: The command function to register
        help_text: Optional help text for the command
    """
    kwargs = {}
    if help_text:
        kwargs["help"] = help_text
    app.command(name, **kwargs)(command)


def register_typer_group(
    app: typer.Typer,
    name: str,
    factory: Callable[[], typer.Typer],
    help_text: str | None = None,
) -> None:
    """Register a sub-typer group on the main app.

    Args:
        app: The main typer app
        name: Group name
        factory: Function that creates the typer sub-app
        help_text: Optional help text for the group
    """
    sub_app = factory()
    app.add_typer(sub_app, name=name, help=help_text)


class CommandRegistry:
    """Registry for CLI command groups."""

    def __init__(self) -> None:
        self._registrars: list[CommandRegistrar] = []

    def register(self, registrar: CommandRegistrar) -> CommandRegistrar:
        """Decorator to register a command group."""
        self._registrars.append(registrar)
        return registrar

    def apply_all(self, app: typer.Typer) -> None:
        """Apply all registered command groups to the main app."""
        for registrar in self._registrars:
            registrar(app)


# Global registry instance
registry = CommandRegistry()
