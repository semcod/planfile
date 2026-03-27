"""Sync with external PM systems (renamed from integrations/).

Canonical location for all PM backend integrations.
"""

# Use local implementations
from planfile.sync.base import TicketRef, TicketStatus, PMBackend
from planfile.sync.generic import GenericBackend
from planfile.sync.github import GitHubBackend
from planfile.sync.mock import MockBackend

# Platform-specific implementations
from planfile.sync.jira import JiraBackend
from planfile.sync.gitlab import GitLabBackend

__all__ = [
    "TicketRef",
    "TicketStatus",
    "PMBackend",
    "GenericBackend",
    "GitHubBackend",
    "MockBackend",
    "JiraBackend",
    "GitLabBackend",
]