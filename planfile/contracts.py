"""Versioned, side-effect-free contracts shared with Planfile producers."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from planfile.core.models import TicketSource

TICKET_PROPOSAL_SCHEMA_ID = "planfile.ticket-proposal.v1"


def _canonical_json(payload: dict) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class TicketProposalSourceV1(BaseModel):
    """Stable provenance supplied by an analyzer, never execution authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tool: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_.-]*$")
    tool_version: str | None = None
    finding_id: str = Field(min_length=1)
    artifact_digest: str | None = Field(
        default=None,
        pattern=r"^(?:sha256:)?[a-fA-F0-9]{64}$",
    )

    @field_validator("tool", "tool_version", "finding_id")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class TicketProposalV1(BaseModel):
    """Analyzer proposal that cannot grant or execute work.

    Queue, sprint, executor, capability, approval, transport and URI fields are
    intentionally absent. ``extra='forbid'`` makes attempts to smuggle any of
    them into a proposal fail before a Planfile ticket can be created.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        strict=True,
    )

    schema_id: Literal["planfile.ticket-proposal.v1"] = Field(
        default=TICKET_PROPOSAL_SCHEMA_ID,
        alias="schema",
    )
    proposal_id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_./:-]*$")
    dedupe_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    priority: Literal["critical", "high", "normal", "low"] = "normal"
    source: TicketProposalSourceV1
    labels: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @field_validator("proposal_id", "dedupe_key", "name", "description")
    @classmethod
    def _strip_scalar(cls, value: str) -> str:
        return value.strip()

    @field_validator("labels", "files", "evidence_refs", mode="before")
    @classmethod
    def _sort_set_like_fields(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        normalized = {str(item).strip() for item in value if str(item).strip()}
        return tuple(sorted(normalized))

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _dedupe_ordered_field(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        result: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return tuple(result)

    def canonical_json(self) -> str:
        return _canonical_json(
            self.model_dump(mode="json", by_alias=True, exclude_none=True),
        )

    @property
    def proposal_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_ticket_kwargs(self) -> dict:
        """Return safe Ticket constructor fields; Koru still chooses queue/sprint/executor."""

        context: dict[str, Any] = {
            "finding_id": self.source.finding_id,
            "proposal_id": self.proposal_id,
            "proposal_hash": self.proposal_hash,
        }
        if self.source.artifact_digest:
            context["artifact_digest"] = self.source.artifact_digest
        if self.evidence_refs:
            context["evidence_refs"] = list(self.evidence_refs)
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "source": TicketSource(
                tool=self.source.tool,
                version=self.source.tool_version,
                context=context,
            ),
            "labels": list(self.labels),
            "files": list(self.files),
            "acceptance_criteria": list(self.acceptance_criteria),
        }


__all__ = [
    "TICKET_PROPOSAL_SCHEMA_ID",
    "TicketProposalSourceV1",
    "TicketProposalV1",
]
