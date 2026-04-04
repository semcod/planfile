"""Shared CLI infrastructure for planfile."""

from planfile.cli.core.console import console, print_dim, print_error, print_info, print_success, print_warning
from planfile.cli.core.errors import exit_with_error, exit_with_warning, handle_exception
from planfile.cli.core.progress import create_progress, with_spinner
from planfile.cli.core.registry import CommandRegistrar, CommandRegistry, registry

__all__ = [
    # Console
    "console",
    "print_success",
    "print_error",
    "print_warning",
    "print_info",
    "print_dim",
    # Errors
    "exit_with_error",
    "exit_with_warning",
    "handle_exception",
    # Progress
    "with_spinner",
    "create_progress",
    # Registry
    "CommandRegistrar",
    "CommandRegistry",
    "registry",
]
