"""Planfile core models - split package for maintainability."""

# Base types
from .base import (
    CACHE_TIMEOUT_SECONDS,
    DAYS_PER_WEEK,
    DEFAULT_SPRINT_LENGTH_DAYS,
    DEFAULT_STRATEGY_VERSION,
    FILE_LOCK_TIMEOUT,
    INITIAL_SPRINT_ID,
    INITIAL_TICKET_ID,
    JSON_INDENT,
    MAX_CACHE_SIZE,
    SECONDS_PER_WEEK,
    ModelTier,
    TaskType,
    TicketStatus,
)

# Strategy models
from .strategy import (
    Goal,
    ModelHints,
    QualityGate,
    Sprint,
    Strategy,
    Task,
    TaskPattern,
)

# Ticket models
from .ticket import (
    Ticket,
    TicketSource,
)

__all__ = [
    # Constants
    "CACHE_TIMEOUT_SECONDS",
    "DAYS_PER_WEEK",
    "DEFAULT_SPRINT_LENGTH_DAYS",
    "DEFAULT_STRATEGY_VERSION",
    "FILE_LOCK_TIMEOUT",
    "INITIAL_SPRINT_ID",
    "INITIAL_TICKET_ID",
    "JSON_INDENT",
    "MAX_CACHE_SIZE",
    "SECONDS_PER_WEEK",
    # Enums
    "ModelTier",
    "TaskType",
    "TicketStatus",
    # Models
    "Goal",
    "ModelHints",
    "QualityGate",
    "Sprint",
    "Strategy",
    "Task",
    "TaskPattern",
    "Ticket",
    "TicketSource",
]
