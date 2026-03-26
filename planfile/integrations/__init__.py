"""Integrations with external PM systems.

Re-exports from softreck-shared for backward compatibility.
"""

try:
    from softreck_shared.integrations import (
        TicketRef,
        TicketStatus,
        PMBackend,
        GenericBackend,
        GitHubBackend,
    )
except ImportError:
    # Fallback to local implementations
    from .base import TicketRef, TicketStatus, PMBackend
    from .generic import GenericBackend
    from .github import GitHubBackend

# Platform-specific implementations
from .jira import JiraBackend
from .gitlab import GitLabBackend

__all__ = [
    "TicketRef",
    "TicketStatus",
    "PMBackend",
    "GenericBackend",
    "GitHubBackend",
    "JiraBackend",
    "GitLabBackend",
]