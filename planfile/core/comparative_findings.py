"""Comparative improvement finding-to-ticket lifecycle adapter.

Owns the single lifecycle boundary that admits comparative improvement findings
(from ``subactor.search/exemplar-gap-policy/v1``, ``t2c.capability-comparison/v1``,
``redup.intent-duplication/v1``, ``intract.scan/v1``, or normalized
``planfile.comparative-finding/v1`` proposals) as idempotent, repository-scoped
Planfile ticket DAGs.

Contract guarantees:
- Reuses ``Planfile.create_ticket_deduplicated``, current storage allocation,
  GitHub sync mapping, and ``expected_updated_at`` CAS preconditions.
- Binds stable deduplication keys to ``(target_repository, capability, intent,
  policy_version, requirement_fingerprint)`` so a refreshed ``evidence_hash``
  appends an occurrence on the active ticket rather than spawning a duplicate,
  while materially changed requirements allocate a distinct ticket.
- When a finding recurs after a terminal ticket (``done`` or ``canceled``),
  allocates a new active successor ticket linked to the prior terminal ticket
  without reopening immutable terminal state.
- Persists actual ``blocked_by``, ``blocks``, ``parent``, and ``children``
  relationships and validates acyclicity and execution layers through
  ``semcod/planfile-graph`` (``planfile_graph``).
- Enforces ``SERVICE``/``FEATURE``/``BUGFIX`` classification with reason,
  target scope, prerequisites, acceptance test, evidence freshness against
  observed target repository HEAD, rollback, and executor ownership, deferring
  target repository governance ticket (``ticket-NNN``) allocation until after
  Planfile admission.
- Supports ``dry_run=True`` with zero ticket, journal, or sync mutations.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from planfile.core.decompose import _check_dag_edges, _dedup, execution_waves
from planfile.core.models import (
    Ticket,
    TicketExecution,
    TicketExecutor,
    TicketInputs,
    TicketOutputs,
    TicketSource,
)
from planfile.core.store import TicketUpdatedAtConflictError

try:
    from planfile_graph import (
        HAS_RUST_GRAPH,
    )
    from planfile_graph import (
        execution_layers as _native_execution_layers,
    )
    from planfile_graph import (
        validate_dag as _native_validate_dag,
    )
except ImportError:
    HAS_RUST_GRAPH = False
    _native_execution_layers = None
    _native_validate_dag = None


COMPARATIVE_FINDING_SCHEMA = "planfile.comparative-finding/v1"
COMPARATIVE_ADMISSION_REPORT_SCHEMA = "planfile.comparative-finding-admission/v1"

ACCEPTED_FINDING_SCHEMAS = frozenset(
    {
        COMPARATIVE_FINDING_SCHEMA,
        "subactor.search/exemplar-gap-policy/v1",
        "t2c.capability-comparison/v1",
        "redup.intent-duplication/v1",
        "intract.scan/v1",
    }
)

CLASSIFICATION_KINDS = frozenset({"SERVICE", "FEATURE", "BUGFIX"})
NO_CHANGE_VERDICTS = frozenset(
    {
        "intentional_difference_preserved",
        "no_change",
        "preserved",
        "satisfied",
    }
)
REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
TERMINAL_RECURRENCE_STATUSES = frozenset({"done", "canceled"})
FAILED_DEPENDENCY_STATUSES = frozenset({"failed", "canceled"})


class ComparativeFindingError(ValueError):
    """Base error for invalid or inadmissible comparative findings."""


class ObsoleteTargetHeadError(ComparativeFindingError):
    """Raised when a finding's target HEAD SHA is stale relative to current HEAD."""


class ComparativeDependencyError(ComparativeFindingError):
    """Raised when prerequisites are missing, failed/canceled, or form a cycle."""


class ExecutorOwnershipSpec(BaseModel):
    """Executor ownership and post-admission governance allocation contract."""

    kind: str = "llm"
    mode: str = "automatic"
    handler: str = "subactor/coding-agent"
    workstream: str = "application"
    queue: str = "default"
    allocate_governance_ticket_after_admission: bool = True
    preallocated_governance_ticket: str | None = None

    @field_validator("kind", "mode", "handler", "workstream", "queue", mode="before")
    @classmethod
    def _require_non_empty_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("executor_ownership_field_empty")
        return text


class ComparativeFindingProposal(BaseModel):
    """Normalized comparative improvement proposal admitted into Planfile."""

    schema_version: str = Field(default=COMPARATIVE_FINDING_SCHEMA, alias="schema")
    finding_id: str
    target_repository: str
    capability: str
    intent: str
    policy_version: str = "v1"
    verdict: str = "actionable_gap"
    classification: Literal["SERVICE", "FEATURE", "BUGFIX"] = "FEATURE"
    classification_reason: str
    target_scope: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    parent_finding_id: str | None = None
    parent_ticket_id: str | None = None
    acceptance_test: list[str] = Field(default_factory=list)
    evidence_hash: str
    target_head_sha: str
    evidence_fresh: bool = True
    rollback: str
    executor_ownership: ExecutorOwnershipSpec = Field(default_factory=ExecutorOwnershipSpec)
    priority: str = "normal"
    sprint: str = "current"
    labels: list[str] = Field(default_factory=list)
    github_issue: dict[str, Any] | None = None
    source_tool: str = "subactor-search"
    source_context: dict[str, Any] = Field(default_factory=dict)
    expected_updated_at: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("schema_version", mode="before")
    @classmethod
    def _validate_schema(cls, value: Any) -> str:
        text = str(value or COMPARATIVE_FINDING_SCHEMA).strip()
        if text not in ACCEPTED_FINDING_SCHEMAS:
            raise ValueError(f"unsupported_finding_schema:{text}")
        return text

    @field_validator(
        "finding_id",
        "capability",
        "intent",
        "policy_version",
        "classification_reason",
        "evidence_hash",
        "rollback",
        mode="before",
    )
    @classmethod
    def _require_non_empty(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("comparative_finding_required_field_empty")
        return text

    @field_validator("target_repository", mode="before")
    @classmethod
    def _validate_repo(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not REPO_SLUG_RE.fullmatch(text):
            raise ValueError(f"invalid_target_repository:{text}")
        return text

    @field_validator("target_head_sha", mode="before")
    @classmethod
    def _validate_head_sha(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not GIT_SHA_RE.fullmatch(text):
            raise ValueError(f"invalid_target_head_sha:{text}")
        return text.lower()

    @field_validator("classification", mode="before")
    @classmethod
    def _validate_classification(cls, value: Any) -> str:
        text = str(value or "").strip().upper()
        if text not in CLASSIFICATION_KINDS:
            raise ValueError(f"invalid_classification:{value}")
        return text

    @field_validator("target_scope", "acceptance_test", mode="before")
    @classmethod
    def _normalize_string_list(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            items = [value.strip()] if value.strip() else []
        elif isinstance(value, (list, tuple, set)):
            items = [str(item).strip() for item in value if str(item or "").strip()]
        else:
            items = []
        return _dedup(items)

    @field_validator("prerequisites", "labels", mode="before")
    @classmethod
    def _normalize_optional_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, (list, tuple, set)):
            return _dedup([str(item).strip() for item in value if str(item or "").strip()])
        return []

    @field_validator("executor_ownership", mode="before")
    @classmethod
    def _normalize_executor_ownership(cls, value: Any) -> Any:
        if value is None:
            return ExecutorOwnershipSpec()
        if isinstance(value, ExecutorOwnershipSpec):
            return value
        if isinstance(value, str):
            handler = value.strip()
            if not handler:
                raise ValueError("executor_ownership_empty")
            return ExecutorOwnershipSpec(handler=handler)
        if isinstance(value, dict):
            return ExecutorOwnershipSpec(**value)
        raise ValueError("invalid_executor_ownership")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_token(value: str, *, max_len: int = 32) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return (cleaned or "item")[:max_len].rstrip("-")


def compute_requirement_fingerprint(proposal: ComparativeFindingProposal) -> str:
    """Digest material requirements so changed requirements do not collide."""
    canonical = {
        "target_repository": proposal.target_repository.lower(),
        "capability": " ".join(proposal.capability.lower().split()),
        "intent": " ".join(proposal.intent.lower().split()),
        "policy_version": proposal.policy_version.strip(),
        "classification": proposal.classification,
        "target_scope": sorted(proposal.target_scope),
        "acceptance_test": sorted(proposal.acceptance_test),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_comparative_dedupe_key(proposal: ComparativeFindingProposal) -> str:
    """Stable deduplication key bound to repo, capability, intent, policy & requirements.

    Refreshed ``evidence_hash`` values intentionally produce the same key so
    they append an occurrence to the existing active ticket instead of spawning
    a duplicate, whereas material requirement changes produce a distinct key.
    """
    req_digest = compute_requirement_fingerprint(proposal)[:16]
    repo_slug = _slug_token(proposal.target_repository, max_len=36)
    cap_slug = _slug_token(proposal.capability, max_len=28)
    pol_slug = _slug_token(proposal.policy_version, max_len=16)
    return f"comparative:{repo_slug}:{cap_slug}:{pol_slug}:{req_digest}"


def _validate_proposal_admission_invariants(
    proposal: ComparativeFindingProposal,
    *,
    current_target_heads: dict[str, str] | None = None,
) -> None:
    if proposal.verdict in NO_CHANGE_VERDICTS:
        return
    if not proposal.target_scope:
        raise ComparativeFindingError(
            f"target_scope_required:{proposal.finding_id}"
        )
    if not proposal.acceptance_test:
        raise ComparativeFindingError(
            f"acceptance_test_required:{proposal.finding_id}"
        )
    ownership = proposal.executor_ownership
    if (
        not ownership.allocate_governance_ticket_after_admission
        or ownership.preallocated_governance_ticket
    ):
        raise ComparativeFindingError(
            f"governance_ticket_must_be_allocated_after_admission:{proposal.finding_id}"
        )
    if not proposal.evidence_fresh:
        raise ObsoleteTargetHeadError(
            f"obsolete_target_evidence:{proposal.finding_id}:{proposal.target_head_sha}"
        )
    if current_target_heads and proposal.target_repository in current_target_heads:
        expected_head = str(current_target_heads[proposal.target_repository] or "").strip().lower()
        observed_head = proposal.target_head_sha.lower()
        if expected_head and not (
            expected_head == observed_head
            or expected_head.startswith(observed_head)
            or observed_head.startswith(expected_head)
        ):
            raise ObsoleteTargetHeadError(
                f"obsolete_target_head:{proposal.finding_id}:"
                f"observed={observed_head}!=current={expected_head}"
            )


def _normalize_github_sync_ref(
    target_repository: str,
    github_issue: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not github_issue or not isinstance(github_issue, dict):
        return None
    raw_id = github_issue.get("id") or github_issue.get("issue") or github_issue.get("number")
    if raw_id is None or str(raw_id).strip() == "":
        return None
    issue_id = str(raw_id).strip()
    repo = str(github_issue.get("repository") or target_repository).strip()
    url = str(
        github_issue.get("url")
        or f"https://github.com/{repo}/issues/{issue_id}"
    )
    key = str(github_issue.get("key") or f"{repo}#{issue_id}")
    return {
        "id": issue_id,
        "issue": int(issue_id) if issue_id.isdigit() else issue_id,
        "repository": repo,
        "url": url,
        "key": key,
    }


def _find_terminal_recurrence_ticket(
    pf: Any,
    dedupe_key: str,
) -> dict[str, Any] | None:
    """Find the most recent terminal ticket carrying ``dedupe:<dedupe_key>``."""
    label = f"dedupe:{dedupe_key}"
    matches: list[dict[str, Any]] = []
    for record in pf.store.ticket_records(sprint="all"):
        labels = record.get("labels") or []
        status = str(record.get("status") or "").lower()
        if label in labels and status in TERMINAL_RECURRENCE_STATUSES:
            matches.append(record)
    if not matches:
        return None
    matches.sort(
        key=lambda rec: (
            str(rec.get("updated_at") or rec.get("created_at") or ""),
            str(rec.get("id") or ""),
        )
    )
    return matches[-1]


def _compute_dag_layers(
    node_ids: list[str],
    edges: list[tuple[str, str]],
) -> tuple[bool, list[str], list[list[str]]]:
    """Validate DAG acyclicity and compute execution layers via planfile_graph."""
    ordered_nodes = _dedup(node_ids)
    is_dag, cycle_nodes = _check_dag_edges(edges, ordered_nodes)
    if not is_dag:
        return False, cycle_nodes, []
    if HAS_RUST_GRAPH and _native_execution_layers is not None:
        try:
            layers = _native_execution_layers(
                ordered_nodes,
                edges,
                prerequisite_first=True,
            )
            return True, [], [list(layer) for layer in layers]
        except Exception:
            pass
    from planfile.core.decompose import _kahn_execution_waves

    return True, [], _kahn_execution_waves(ordered_nodes, edges)


def _occurrence_entry(proposal: ComparativeFindingProposal) -> dict[str, Any]:
    return {
        "finding_id": proposal.finding_id,
        "evidence_hash": proposal.evidence_hash,
        "target_head_sha": proposal.target_head_sha,
        "policy_version": proposal.policy_version,
        "requirement_fingerprint": compute_requirement_fingerprint(proposal),
    }


def _ticket_occurrences(ticket: Ticket) -> list[dict[str, Any]]:
    if ticket.outputs and isinstance(ticket.outputs.result, dict):
        items = ticket.outputs.result.get("comparative_occurrences")
        if isinstance(items, list):
            return [dict(item) for item in items if isinstance(item, dict)]
    if ticket.source and isinstance(ticket.source.context, dict):
        items = ticket.source.context.get("comparative_occurrences")
        if isinstance(items, list):
            return [dict(item) for item in items if isinstance(item, dict)]
    return []


def _append_occurrence_with_cas(
    pf: Any,
    ticket: Ticket,
    proposal: ComparativeFindingProposal,
    *,
    desired_blocked_by: list[str] | None = None,
    desired_parent: str | None = None,
    desired_sync_github: dict[str, Any] | None = None,
) -> tuple[Ticket, Literal["deduplicated_unchanged", "occurrence_appended", "sync_updated"]]:
    """Idempotently refresh an active ticket using ``expected_updated_at`` CAS."""
    current = pf.get_ticket(ticket.id, repair_index=False) or ticket
    expected_rev = proposal.expected_updated_at or (
        current.updated_at.isoformat()
        if isinstance(current.updated_at, datetime)
        else str(current.updated_at or "")
    )
    occurrences = _ticket_occurrences(current)
    seen_hashes = {str(item.get("evidence_hash") or "") for item in occurrences}
    is_new_occurrence = proposal.evidence_hash not in seen_hashes

    merged_blocked_by = _dedup(
        [*(current.blocked_by or []), *(desired_blocked_by or [])]
    )
    blocked_by_changed = merged_blocked_by != list(current.blocked_by or [])

    effective_parent = desired_parent if desired_parent is not None else current.parent
    parent_changed = effective_parent != current.parent

    current_sync = dict(current.sync or {})
    existing_gh = current_sync.get("github") if isinstance(current_sync.get("github"), dict) else None
    sync_changed = False
    if desired_sync_github is not None and existing_gh != desired_sync_github:
        current_sync["github"] = desired_sync_github
        sync_changed = True

    if not is_new_occurrence and not blocked_by_changed and not parent_changed and not sync_changed:
        # Even when unchanged, if caller supplied an explicit expected_updated_at
        # precondition that does not match the current ticket, fail closed.
        if proposal.expected_updated_at is not None:
            pf.store._guard_expected_updated_at(
                current.model_dump(mode="json", exclude_none=True),
                proposal.expected_updated_at,
            )
        return current, "deduplicated_unchanged"

    new_occurrences = list(occurrences)
    if is_new_occurrence:
        new_occurrences.append(
            {
                **_occurrence_entry(proposal),
                "observed_at": _utcnow_iso(),
            }
        )

    outputs_data = (
        current.outputs.model_dump(mode="python", exclude_none=True)
        if current.outputs
        else {}
    )
    result_data = dict(outputs_data.get("result") or {}) if isinstance(outputs_data.get("result"), dict) else {}
    result_data["comparative_occurrences"] = new_occurrences
    result_data["latest_evidence_hash"] = proposal.evidence_hash
    result_data["latest_target_head_sha"] = proposal.target_head_sha
    result_data["occurrence_count"] = len(new_occurrences)
    outputs_data["result"] = result_data
    notes = list(outputs_data.get("notes") or [])
    if is_new_occurrence:
        note = (
            f"comparative-occurrence:{proposal.finding_id}:"
            f"evidence={proposal.evidence_hash}:head={proposal.target_head_sha}"
        )
        if note not in notes:
            notes.append(note)
    outputs_data["notes"] = notes

    source_data = (
        current.source.model_dump(mode="python", exclude_none=True)
        if current.source
        else {"tool": proposal.source_tool}
    )
    context_data = dict(source_data.get("context") or {})
    context_data["latest_evidence_hash"] = proposal.evidence_hash
    context_data["latest_target_head_sha"] = proposal.target_head_sha
    context_data["occurrence_count"] = len(new_occurrences)
    context_data["comparative_occurrences"] = new_occurrences
    source_data["context"] = context_data

    updates: dict[str, Any] = {
        "outputs": TicketOutputs(**outputs_data),
        "source": TicketSource(**source_data),
    }
    if blocked_by_changed:
        updates["blocked_by"] = merged_blocked_by
    if parent_changed:
        updates["parent"] = effective_parent
    if sync_changed:
        updates["sync"] = current_sync

    updated = pf.update_ticket(
        current.id,
        reason=(
            f"comparative_occurrence_refresh:{proposal.finding_id}:{proposal.evidence_hash}"
            if is_new_occurrence
            else f"comparative_relationship_or_sync_update:{proposal.finding_id}"
        ),
        actor=f"comparative-adapter:{proposal.source_tool}",
        expected_updated_at=expected_rev,
        **updates,
    )
    if updated is None:
        raise ComparativeFindingError(f"ticket_disappeared_during_refresh:{current.id}")
    outcome: Literal["occurrence_appended", "sync_updated"] = (
        "occurrence_appended" if is_new_occurrence else "sync_updated"
    )
    return updated, outcome


def admit_comparative_findings(
    pf: Any,
    findings: list[ComparativeFindingProposal | dict[str, Any]],
    *,
    current_target_heads: dict[str, str] | None = None,
    sprint: str = "current",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Admit comparative improvement findings as idempotent repository-scoped ticket DAGs.

    Parameters
    ----------
    pf:
        Live ``Planfile`` facade instance.
    findings:
        List of ``ComparativeFindingProposal`` instances or compatible dicts.
    current_target_heads:
        Optional mapping of ``{"owner/repo": "<current_head_sha>"}`` used to
        reject findings bound to an obsolete target repository HEAD.
    sprint:
        Target sprint for newly admitted tickets (defaults to ``"current"``).
    dry_run:
        When ``True``, validates all proposals, computes deduplication/recurrence
        decisions and ``planfile_graph`` DAG execution layers, and returns the
        admission report without mutating storage or external sync state.
    """
    proposals: list[ComparativeFindingProposal] = [
        item
        if isinstance(item, ComparativeFindingProposal)
        else ComparativeFindingProposal.model_validate(item)
        for item in findings
    ]

    # 1. Partition no-change findings vs actionable proposals and validate invariants.
    actionable: list[ComparativeFindingProposal] = []
    decisions: list[dict[str, Any]] = []
    by_finding_id: dict[str, ComparativeFindingProposal] = {}

    for proposal in proposals:
        if proposal.finding_id in by_finding_id:
            raise ComparativeFindingError(
                f"duplicate_finding_id_in_batch:{proposal.finding_id}"
            )
        by_finding_id[proposal.finding_id] = proposal

        if proposal.verdict in NO_CHANGE_VERDICTS:
            decisions.append(
                {
                    "finding_id": proposal.finding_id,
                    "target_repository": proposal.target_repository,
                    "capability": proposal.capability,
                    "outcome": "no_change",
                    "verdict": proposal.verdict,
                    "ticket_id": None,
                    "dedupe_key": compute_comparative_dedupe_key(proposal),
                    "mutated": False,
                }
            )
            continue

        _validate_proposal_admission_invariants(
            proposal,
            current_target_heads=current_target_heads,
        )
        actionable.append(proposal)

    # 2. Validate prerequisites & parent references before any ticket mutation.
    existing_tickets = {
        t.id: t for t in pf.list_tickets(sprint="all")
    }
    actionable_ids = {p.finding_id for p in actionable}
    no_change_ids = {
        d["finding_id"] for d in decisions if d["outcome"] == "no_change"
    }

    for proposal in actionable:
        for prereq in proposal.prerequisites:
            if prereq == proposal.finding_id:
                raise ComparativeDependencyError(
                    f"self_dependency_forbidden:{proposal.finding_id}"
                )
            if prereq in no_change_ids:
                raise ComparativeDependencyError(
                    f"prerequisite_not_admitted_no_change:{proposal.finding_id}->{prereq}"
                )
            if prereq in actionable_ids:
                continue
            existing_dep = existing_tickets.get(prereq)
            if existing_dep is None:
                raise ComparativeDependencyError(
                    f"prerequisite_not_found:{proposal.finding_id}->{prereq}"
                )
            dep_status = (
                existing_dep.status.value
                if hasattr(existing_dep.status, "value")
                else str(existing_dep.status)
            ).lower()
            if dep_status in FAILED_DEPENDENCY_STATUSES:
                raise ComparativeDependencyError(
                    f"prerequisite_in_failed_state:{proposal.finding_id}->{prereq}:{dep_status}"
                )

        if proposal.parent_finding_id:
            if proposal.parent_finding_id == proposal.finding_id:
                raise ComparativeDependencyError(
                    f"self_parent_forbidden:{proposal.finding_id}"
                )
            if proposal.parent_finding_id not in actionable_ids:
                raise ComparativeDependencyError(
                    f"parent_finding_not_found:{proposal.finding_id}->{proposal.parent_finding_id}"
                )
        if proposal.parent_ticket_id:
            parent_existing = existing_tickets.get(proposal.parent_ticket_id)
            if parent_existing is None:
                raise ComparativeDependencyError(
                    f"parent_ticket_not_found:{proposal.finding_id}->{proposal.parent_ticket_id}"
                )
            parent_status = (
                parent_existing.status.value
                if hasattr(parent_existing.status, "value")
                else str(parent_existing.status)
            ).lower()
            if parent_status in FAILED_DEPENDENCY_STATUSES:
                raise ComparativeDependencyError(
                    f"parent_ticket_in_failed_state:{proposal.finding_id}->{proposal.parent_ticket_id}:{parent_status}"
                )

    # 3. Validate batch-level DAG (including existing ticket dependencies) via planfile_graph
    #    BEFORE allocating or mutating any tickets!
    preview_nodes: list[str] = [
        *[t.id for t in existing_tickets.values()],
        *[f"finding:{p.finding_id}" for p in actionable],
    ]
    preview_edges: list[tuple[str, str]] = [
        *[
            (t.id, dep)
            for t in existing_tickets.values()
            for dep in (t.blocked_by or [])
            if dep in existing_tickets
        ],
    ]
    for proposal in actionable:
        node_key = f"finding:{proposal.finding_id}"
        for prereq in proposal.prerequisites:
            target_key = (
                f"finding:{prereq}" if prereq in actionable_ids else prereq
            )
            preview_edges.append((node_key, target_key))
        if proposal.parent_finding_id:
            # Parent epic is blocked by its child subtasks only when explicitly requested
            # via prerequisites; parent->child hierarchy itself must also be acyclic.
            preview_edges.append((f"finding:{proposal.parent_finding_id}", node_key))

    is_dag, cycle_nodes, preview_layers = _compute_dag_layers(preview_nodes, preview_edges)
    if not is_dag:
        raise ComparativeDependencyError(
            f"comparative_finding_cycle_detected:{cycle_nodes}"
        )

    # 4. If dry_run=True, compute exact deduplication/recurrence preview without mutating store.
    if dry_run:
        live_by_label: dict[str, Ticket] = {}
        for ticket in existing_tickets.values():
            st = (
                ticket.status.value
                if hasattr(ticket.status, "value")
                else str(ticket.status)
            ).lower()
            if st in TERMINAL_RECURRENCE_STATUSES:
                continue
            for label in ticket.labels or []:
                if label.startswith("dedupe:"):
                    live_by_label.setdefault(label, ticket)

        for proposal in actionable:
            dedupe_key = compute_comparative_dedupe_key(proposal)
            dedupe_label = f"dedupe:{dedupe_key}"
            live_match = live_by_label.get(dedupe_label)
            terminal_match = (
                None
                if live_match is not None
                else _find_terminal_recurrence_ticket(pf, dedupe_key)
            )
            if live_match is not None:
                seen_hashes = {
                    str(item.get("evidence_hash") or "")
                    for item in _ticket_occurrences(live_match)
                }
                planned_outcome = (
                    "deduplicated_unchanged"
                    if proposal.evidence_hash in seen_hashes
                    else "occurrence_appended"
                )
                ticket_id = live_match.id
            elif terminal_match is not None:
                planned_outcome = "recurrence_created"
                ticket_id = None
            else:
                planned_outcome = "created"
                ticket_id = None

            decisions.append(
                {
                    "finding_id": proposal.finding_id,
                    "target_repository": proposal.target_repository,
                    "capability": proposal.capability,
                    "classification": proposal.classification,
                    "classification_reason": proposal.classification_reason,
                    "outcome": planned_outcome,
                    "ticket_id": ticket_id,
                    "dedupe_key": dedupe_key,
                    "requirement_fingerprint": compute_requirement_fingerprint(proposal),
                    "recurs_from_ticket_id": (
                        str(terminal_match.get("id")) if terminal_match else None
                    ),
                    "governance_ticket_allocation": "deferred_until_post_admission",
                    "mutated": False,
                }
            )

        return {
            "schema": COMPARATIVE_ADMISSION_REPORT_SCHEMA,
            "dry_run": True,
            "sprint": sprint,
            "admitted_count": len(actionable),
            "no_change_count": sum(1 for d in decisions if d["outcome"] == "no_change"),
            "decisions": decisions,
            "dag_valid": True,
            "execution_layers": preview_layers,
        }

    # 5. Admit actionable proposals using create_ticket_deduplicated + CAS updates.
    finding_to_ticket_id: dict[str, str] = {}
    admitted_tickets: dict[str, Ticket] = {}
    proposal_outcomes: dict[str, str] = {}
    recurrence_origins: dict[str, str | None] = {}

    for proposal in actionable:
        dedupe_key = compute_comparative_dedupe_key(proposal)
        req_fingerprint = compute_requirement_fingerprint(proposal)
        prior_terminal = _find_terminal_recurrence_ticket(pf, dedupe_key)
        prior_terminal_id = str(prior_terminal.get("id")) if prior_terminal else None
        recurrence_origins[proposal.finding_id] = prior_terminal_id

        initial_occurrence = {
            **_occurrence_entry(proposal),
            "observed_at": _utcnow_iso(),
        }
        labels = _dedup(
            [
                *proposal.labels,
                f"repo:{proposal.target_repository}",
                f"capability:{_slug_token(proposal.capability, max_len=36)}",
                f"kind:{proposal.classification.lower()}",
                f"policy:{proposal.policy_version}",
                "comparative-finding",
                *(
                    [f"recurs-from:{prior_terminal_id}"]
                    if prior_terminal_id
                    else []
                ),
            ]
        )

        ownership = proposal.executor_ownership
        executor = TicketExecutor(
            kind=ownership.kind,
            mode=ownership.mode,
            handler=ownership.handler,
        )
        execution = TicketExecution(
            queue=ownership.queue,
            state="pending",
        )
        inputs = TicketInputs(
            context_files=list(proposal.target_scope),
            verify_command=proposal.acceptance_test[0] if proposal.acceptance_test else None,
        )
        outputs = TicketOutputs(
            notes=[
                f"comparative-occurrence:{proposal.finding_id}:"
                f"evidence={proposal.evidence_hash}:head={proposal.target_head_sha}"
            ],
            result={
                "comparative_occurrences": [initial_occurrence],
                "latest_evidence_hash": proposal.evidence_hash,
                "latest_target_head_sha": proposal.target_head_sha,
                "occurrence_count": 1,
                "requirement_fingerprint": req_fingerprint,
                "classification": proposal.classification,
                "classification_reason": proposal.classification_reason,
                "rollback": proposal.rollback,
                "governance_ticket_allocation": "deferred_until_post_admission",
                "recurs_from_ticket_id": prior_terminal_id,
            },
        )
        source_context = {
            **proposal.source_context,
            "schema": proposal.schema_version,
            "finding_id": proposal.finding_id,
            "target_repository": proposal.target_repository,
            "capability": proposal.capability,
            "intent": proposal.intent,
            "policy_version": proposal.policy_version,
            "classification": proposal.classification,
            "classification_reason": proposal.classification_reason,
            "target_scope": list(proposal.target_scope),
            "acceptance_test": list(proposal.acceptance_test),
            "rollback": proposal.rollback,
            "executor_ownership": ownership.model_dump(mode="json"),
            "governance_ticket_allocation": "deferred_until_post_admission",
            "requirement_fingerprint": req_fingerprint,
            "latest_evidence_hash": proposal.evidence_hash,
            "latest_target_head_sha": proposal.target_head_sha,
            "occurrence_count": 1,
            "comparative_occurrences": [initial_occurrence],
            "recurs_from_ticket_id": prior_terminal_id,
        }
        source = TicketSource(
            tool=proposal.source_tool,
            version=proposal.policy_version,
            context=source_context,
        )
        sync_github = _normalize_github_sync_ref(
            proposal.target_repository,
            proposal.github_issue,
        )
        sync_dict = {"github": sync_github} if sync_github else {}

        description = (
            f"[{proposal.classification}] {proposal.target_repository} — {proposal.capability}: "
            f"{proposal.intent}\n\n"
            f"Classification reason: {proposal.classification_reason}\n"
            f"Rollback: {proposal.rollback}"
        )

        ticket, created = pf.create_ticket_deduplicated(
            name=f"[{proposal.target_repository}] {proposal.capability}: {proposal.intent}",
            priority=proposal.priority,
            sprint=proposal.sprint or sprint,
            description=description,
            acceptance_criteria=list(proposal.acceptance_test),
            labels=labels,
            files=list(proposal.target_scope),
            executor=executor,
            execution=execution,
            inputs=inputs,
            outputs=outputs,
            source=source,
            sync=sync_dict,
            dedupe_key=dedupe_key,
        )

        finding_to_ticket_id[proposal.finding_id] = ticket.id
        if created:
            admitted_tickets[proposal.finding_id] = ticket
            proposal_outcomes[proposal.finding_id] = (
                "recurrence_created" if prior_terminal_id else "created"
            )
        else:
            refreshed, refresh_outcome = _append_occurrence_with_cas(
                pf,
                ticket,
                proposal,
                desired_sync_github=sync_github,
            )
            admitted_tickets[proposal.finding_id] = refreshed
            proposal_outcomes[proposal.finding_id] = refresh_outcome

    # 6. Wire actual blocked_by, blocks, parent, and children relationships across
    #    the admitted DAG using expected_updated_at CAS updates.
    parent_children_map: dict[str, list[str]] = {}
    blocker_blocks_map: dict[str, list[str]] = {}

    for proposal in actionable:
        ticket_id = finding_to_ticket_id[proposal.finding_id]
        resolved_prereqs = _dedup(
            [
                finding_to_ticket_id.get(prereq, prereq)
                for prereq in proposal.prerequisites
            ]
        )
        for dep_id in resolved_prereqs:
            blocker_blocks_map.setdefault(dep_id, []).append(ticket_id)

        resolved_parent: str | None = None
        if proposal.parent_finding_id:
            resolved_parent = finding_to_ticket_id[proposal.parent_finding_id]
        elif proposal.parent_ticket_id:
            resolved_parent = proposal.parent_ticket_id

        if resolved_parent:
            parent_children_map.setdefault(resolved_parent, []).append(ticket_id)

        current = pf.get_ticket(ticket_id, repair_index=False) or admitted_tickets[proposal.finding_id]
        merged_blocked_by = _dedup([*(current.blocked_by or []), *resolved_prereqs])
        effective_parent = resolved_parent if resolved_parent is not None else current.parent
        rel_updates: dict[str, Any] = {}
        if merged_blocked_by != list(current.blocked_by or []):
            rel_updates["blocked_by"] = merged_blocked_by
        if effective_parent != current.parent:
            rel_updates["parent"] = effective_parent
        if rel_updates:
            expected_rev = (
                current.updated_at.isoformat()
                if isinstance(current.updated_at, datetime)
                else str(current.updated_at or "")
            )
            updated = pf.update_ticket(
                ticket_id,
                reason=f"comparative_dag_wiring:{proposal.finding_id}",
                actor=f"comparative-adapter:{proposal.source_tool}",
                expected_updated_at=expected_rev,
                **rel_updates,
            )
            if updated is not None:
                admitted_tickets[proposal.finding_id] = updated

    # Persist inverse children and blocks pointers on parents/blockers with CAS.
    for parent_id, child_ids in parent_children_map.items():
        parent_ticket = pf.get_ticket(parent_id, repair_index=False)
        if parent_ticket is None:
            continue
        merged_children = _dedup([*(parent_ticket.children or []), *child_ids])
        if merged_children != list(parent_ticket.children or []):
            expected_rev = (
                parent_ticket.updated_at.isoformat()
                if isinstance(parent_ticket.updated_at, datetime)
                else str(parent_ticket.updated_at or "")
            )
            pf.update_ticket(
                parent_id,
                children=merged_children,
                reason="comparative_parent_children_wiring",
                actor="comparative-adapter",
                expected_updated_at=expected_rev,
            )

    for blocker_id, dependent_ids in blocker_blocks_map.items():
        blocker_ticket = pf.get_ticket(blocker_id, repair_index=False)
        if blocker_ticket is None:
            continue
        merged_blocks = _dedup([*(blocker_ticket.blocks or []), *dependent_ids])
        if merged_blocks != list(blocker_ticket.blocks or []):
            expected_rev = (
                blocker_ticket.updated_at.isoformat()
                if isinstance(blocker_ticket.updated_at, datetime)
                else str(blocker_ticket.updated_at or "")
            )
            pf.update_ticket(
                blocker_id,
                blocks=merged_blocks,
                reason="comparative_blocker_blocks_wiring",
                actor="comparative-adapter",
                expected_updated_at=expected_rev,
            )

    # 7. Finalize decisions and compute authoritative execution layers via planfile_graph.
    for proposal in actionable:
        ticket_id = finding_to_ticket_id[proposal.finding_id]
        final_ticket = pf.get_ticket(ticket_id, repair_index=False) or admitted_tickets[proposal.finding_id]
        admitted_tickets[proposal.finding_id] = final_ticket
        outcome = proposal_outcomes[proposal.finding_id]
        decisions.append(
            {
                "finding_id": proposal.finding_id,
                "target_repository": proposal.target_repository,
                "capability": proposal.capability,
                "classification": proposal.classification,
                "classification_reason": proposal.classification_reason,
                "outcome": outcome,
                "ticket_id": final_ticket.id,
                "dedupe_key": compute_comparative_dedupe_key(proposal),
                "requirement_fingerprint": compute_requirement_fingerprint(proposal),
                "blocked_by": list(final_ticket.blocked_by or []),
                "blocks": list(final_ticket.blocks or []),
                "parent": final_ticket.parent,
                "children": list(final_ticket.children or []),
                "occurrence_count": len(_ticket_occurrences(final_ticket)),
                "recurs_from_ticket_id": recurrence_origins.get(proposal.finding_id),
                "governance_ticket_allocation": "deferred_until_post_admission",
                "mutated": outcome != "deduplicated_unchanged",
            }
        )

    layers = execution_waves(pf, sprint=sprint)
    return {
        "schema": COMPARATIVE_ADMISSION_REPORT_SCHEMA,
        "dry_run": False,
        "sprint": sprint,
        "admitted_count": len(actionable),
        "no_change_count": sum(1 for d in decisions if d["outcome"] == "no_change"),
        "decisions": decisions,
        "dag_valid": True,
        "execution_layers": layers,
    }


__all__ = [
    "ACCEPTED_FINDING_SCHEMAS",
    "CLASSIFICATION_KINDS",
    "COMPARATIVE_ADMISSION_REPORT_SCHEMA",
    "COMPARATIVE_FINDING_SCHEMA",
    "ComparativeDependencyError",
    "ComparativeFindingError",
    "ComparativeFindingProposal",
    "ExecutorOwnershipSpec",
    "ObsoleteTargetHeadError",
    "TicketUpdatedAtConflictError",
    "admit_comparative_findings",
    "compute_comparative_dedupe_key",
    "compute_requirement_fingerprint",
]
