"""Sync with external PM systems (renamed from integrations/).

Canonical location for all PM backend integrations.
"""

# Use local implementations
from planfile.sync.base import PMBackend, TicketRef, TicketState
from planfile.sync.generic import GenericBackend
from planfile.sync.github import GitHubBackend
from planfile.sync.github_projects import GitHubProjectsBackend, GitHubProjectsError
from planfile.sync.gitlab import GitLabBackend

# Platform-specific implementations
from planfile.sync.jira import JiraBackend
from planfile.sync.mock import MockBackend

__all__ = [
    "TicketRef",
    "TicketState",
    "PMBackend",
    "GenericBackend",
    "GitHubBackend",
    "GitHubProjectsBackend",
    "GitHubProjectsError",
    "MockBackend",
    "JiraBackend",
    "GitLabBackend",
]
