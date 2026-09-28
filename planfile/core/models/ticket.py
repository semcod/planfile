"""Ticket models - atomic unit of work in planfile."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, StrictBool, field_validator, model_serializer

from .base import TicketStatus
from .strategy import ModelHints

TICKET_CONTRACT_VERSION = "planfile.ticket/v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TicketSource(BaseModel):
    """Who/what created the ticket."""
    tool: str                          # "code2llm" | "vallm" | "llx" | "human"
    version: str | None = None
    timestamp: datetime = Field(default_factory=_utcnow)
    context: dict = Field(default_factory=dict)


class TicketExecutor(BaseModel):
    """Who should execute this task and by what mechanism."""

    kind: str = "human"  # human | shell | mcp | api | llm
    mode: str = "interactive"  # interactive | automatic
    handler: str | None = None


class TicketExecution(BaseModel):
    """Runtime execution state for queue-oriented workflows."""

    queue: str = "default"
    state: str = "pending"  # pending | ready | running | waiting_input | done | failed | skipped
    assigned_to: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    lease_expires_at: datetime | None = None
    attempt: int = 0
    max_attempts: int = 1
    last_error: str | None = None


class TicketUriProcess(BaseModel):
    """One named URI-addressed process expected while completing a ticket."""

    id: str
    name: str
    uri: str
    actor: str = "system"
    payload: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    human_approval: bool = False
    status: str = "pending"


class TicketInputs(BaseModel):
    """Inputs required before or during execution."""

    prompt: str | None = None
    env_keys: list[str] = Field(default_factory=list)
    script: str | None = None
    expect_files_changed: StrictBool = False
    api_endpoint: str | None = None
    api_method: str = "GET"
    api_headers: dict[str, str] = Field(default_factory=dict)
    api_body: Any = None
    api_timeout_seconds: float = 30.0
    mcp_tool: str | None = None
    llm_model: str | None = None
    # Explicit execution inputs consumed by Koru's context assembler/runner.
    # None keeps legacy tickets from acquiring implicit context or time limits.
    context_files: list[str] | None = None
    context_globs: list[str] | None = None
    include_project_context: StrictBool | None = None
    max_context_chars: int | None = None
    llm_timeout_seconds: float | None = None
    uri_processes: list[TicketUriProcess] = Field(default_factory=list)
    # Structured process contract. Legacy clients may still embed v1 in the
    # description; governed v2 tickets use this field as the authority.
    process_manifest: dict[str, Any] | None = None

    @model_serializer(mode="wrap")
    def serialize_inputs(self, handler):
        """Preserve explicit expectations without overriding legacy inference."""
        data = handler(self)
        if "expect_files_changed" not in self.model_fields_set:
            data.pop("expect_files_changed", None)
        return data


class TicketOutputs(BaseModel):
    """Artifacts and result data produced by execution."""

    artifacts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    result: Any = None
    completion_receipt: dict[str, Any] | None = None


class Ticket(BaseModel):
    """Atomic unit of work in planfile."""
    id: str                            # "PLF-042"
    name: str
    # Missing means the record predates explicit ticket-contract versioning.
    # The store stamps this field only for newly created tickets; merely reading
    # a legacy record must not silently rewrite its provenance.
    contract_version: str | None = None
    status: TicketStatus = TicketStatus.open  # Default to open status

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower().replace("-", "_")
            if normalized in ("closed", "close", "resolved", "completed"):
                return TicketStatus.done
            if normalized in ("in_progress", "inprogress", "doing", "active"):
                return TicketStatus.in_progress
            if normalized in ("todo", "backlog"):
                return TicketStatus.open
            if normalized in ("cancelled", "canceled"):
                return TicketStatus.canceled
            try:
                return TicketStatus(normalized)
            except ValueError:
                pass
        return value

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("medium", "med"):
                return "normal"
            return normalized
        return value

    priority: str = "normal"           # critical | high | normal | low
    sprint: str = "current"            # current | backlog | sprint-XXX

    source: TicketSource | None = None
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)

    blocked_by: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)

    # Git-like decomposition: a ticket can be split into smaller subtasks (children) that
    # roll up to a parent, and related tickets can be gathered under a named group (epic).
    parent: str | None = None                          # this ticket is a subtask of `parent`
    children: list[str] = Field(default_factory=list)  # decomposed subtask ticket IDs
    group: str | None = None                           # epic/group name for related tickets

    file: str | None = None  # Single file path (for backward compatibility)
    files: list[str] = Field(default_factory=list)  # Files associated with this ticket

    integration: list[str] | None = None  # Target integrations for sync

    llm_hints: ModelHints | None = None
    executor: TicketExecutor | None = None
    execution: TicketExecution | None = None
    inputs: TicketInputs | None = None
    outputs: TicketOutputs | None = None

    sync: dict = Field(default_factory=dict)  # {"github": {"issue": 142}}
    history: list[dict] = Field(default_factory=list)
    # Canonical, reversible creation event. Subsequent replay events live in
    # events/operations.jsonl; history retains compact audit metadata.
    dsl: str | None = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
