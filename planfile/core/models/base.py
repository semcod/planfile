"""Base enums and constants for planfile models."""

from __future__ import annotations

from enum import Enum

# Constants
DEFAULT_SPRINT_LENGTH_DAYS = 14
DEFAULT_STRATEGY_VERSION = "1.0.0"
INITIAL_SPRINT_ID = 1
INITIAL_TICKET_ID = 1
SECONDS_PER_WEEK = 7
CACHE_TIMEOUT_SECONDS = 30
MAX_CACHE_SIZE = 100
FILE_LOCK_TIMEOUT = 5
DAYS_PER_WEEK = 7
JSON_INDENT = 2


class TaskType(str, Enum):
    """Type of task in the planfile."""
    feature = "feature"
    tech_debt = "tech_debt"
    bug = "bug"
    chore = "chore"
    documentation = "documentation"
    refactor = "refactor"
    test = "test"


class ModelTier(str, Enum):
    """Model tier for different phases of work."""
    local = "local"
    cheap = "cheap"
    balanced = "balanced"
    premium = "premium"
    free = "free"  # Alias for cheap


class TicketStatus(str, Enum):
    """Status of a ticket."""
    open = "open"
    in_progress = "in_progress"
    review = "review"
    done = "done"
    blocked = "blocked"
