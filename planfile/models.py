"""Backward compatibility — import from core.models."""
from planfile.core.models import (
    TaskType, ModelTier, ModelHints, Task, TaskPattern,
    Sprint, Goal, QualityGate, Strategy,
    Ticket, TicketStatus, TicketSource,
)

__all__ = [
    "TaskType", "ModelTier", "ModelHints", "Task", "TaskPattern",
    "Sprint", "Goal", "QualityGate", "Strategy",
    "Ticket", "TicketStatus", "TicketSource",
]
