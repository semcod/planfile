"""Sync with external PM systems (renamed from integrations/).

Canonical location for all PM backend integrations.
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