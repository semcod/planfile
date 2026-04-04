"""Command registry for organizing CLI commands."""

from typing import Callable

import typer

# Type alias for command registration functions
CommandRegistrar = Callable[[typer.Typer], None]


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
