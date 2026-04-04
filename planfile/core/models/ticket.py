"""Ticket models - atomic unit of work in planfile."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .base import ModelTier


class TicketSource(BaseModel):
    """Who/what created the ticket."""
    tool: str                          # "code2llm" | "vallm" | "llx" | "human"
    version: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: dict = Field(default_factory=dict)


class Ticket(BaseModel):
    """Atomic unit of work in planfile."""
    id: str                            # "PLF-042"
    title: str
    status: "TicketStatus" = None      # Forward reference
    priority: str = "normal"           # critical | high | normal | low
    sprint: str = "current"            # current | backlog | sprint-XXX

    source: TicketSource | None = None
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)

    blocked_by: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)

    integration: list[str] | None = None  # Target integrations for sync

    llm_hints: ModelHints | None = None

    sync: dict = Field(default_factory=dict)  # {"github": {"issue": 142}}
    history: list[dict] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Set default status if not provided."""
        if self.status is None:
            from .base import TicketStatus
            self.status = TicketStatus.open
