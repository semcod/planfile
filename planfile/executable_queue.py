"""Canonical executable pending queue specification shared across Planfile, Heyasa, and monag."""

from __future__ import annotations

import os
import sys
import types
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from planfile.contracts import (
    EXECUTABLE_QUEUE_SCHEMA,
    ExecutableCandidateV1,
    ExecutableQueueCountsV1,
    ExecutableQueueSummaryV1,
    ExecutableSkippedItemV1,
)
from planfile.core.models import Ticket
from planfile.reconcile import (
    SlugIndex,
    TargetRepoObservation,
    _deferred_slug_index,
    _utc_now,
    discover_planfile_repositories,
    find_live_ticket_binding,
    iter_sprint_tickets,
    resolve_ticket_target_repo,
)

if TYPE_CHECKING:
    from planfile import Planfile

RUNNABLE_EXECUTION_STATES: frozenset[str] = frozenset({"", "pending", "ready"})
SATISFIED_DEPENDENCY_STATUSES: frozenset[str] = frozenset({"done", "canceled"})
_PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "normal": 2,
    "medium": 2,
    "low": 3,
}


@dataclass(frozen=True)
class CandidateEvaluation:
    """Detailed evaluation outcome for one candidate ticket."""

    executable: bool
    reason: str = ""
    category: str = "executable"
    repo_path: str | None = None
    repository: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "executable": self.executable,
            "reason": self.reason,
            "category": self.category,
            "repo_path": self.repo_path,
            "repository": self.repository,
        }


def _normalize_status(raw: Any) -> str:
    val = raw.value if hasattr(raw, "value") else str(raw or "")
    lowered = val.strip().lower()
    if lowered == "cancelled":
        return "canceled"
    if lowered in {"completed", "closed", "resolved"}:
        return "done"
    return lowered


def _ticket_field(ticket: Ticket | Mapping[str, Any], name: str, default: Any = None) -> Any:
    if isinstance(ticket, Ticket):
        return getattr(ticket, name, default)
    return ticket.get(name, default)


def _extract_exec_state_and_queue(ticket: Ticket | Mapping[str, Any]) -> tuple[str, str]:
    execution = _ticket_field(ticket, "execution")
    if execution is None:
        return "", "default"
    if isinstance(execution, Mapping):
        state = str(execution.get("state") or "").strip().lower()
        queue = str(execution.get("queue") or "default").strip() or "default"
        return state, queue
    state = str(getattr(execution, "state", "") or "").strip().lower()
    queue = str(getattr(execution, "queue", "default") or "default").strip() or "default"
    return state, queue


def _check_autonomy_and_goal(ticket: Ticket | Mapping[str, Any]) -> tuple[str, str]:
    if os.environ.get("PLANFILE_NO_AUTONOMY_FILTER") != "1":
        require_envelope = os.environ.get(
            "PLANFILE_REQUIRE_PROCESS_ENVELOPE", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        if require_envelope:
            inputs = _ticket_field(ticket, "inputs")
            manifest = (
                inputs.get("process_manifest")
                if isinstance(inputs, Mapping)
                else getattr(inputs, "process_manifest", None)
            )
            if (
                not isinstance(manifest, Mapping)
                or manifest.get("schema") != "subactor.process-envelope.v2"
            ):
                return "process-envelope-required", "process_envelope"
            definitions = manifest.get("definitions")
            valid = (
                bool(str(manifest.get("reason") or "").strip())
                and bool(str(manifest.get("requested_by") or "").strip())
                and isinstance(definitions, Mapping)
                and all(
                    isinstance(definitions.get(kind), list) and definitions[kind]
                    for kind in ("aql", "eql", "oql", "uri")
                )
            )
            if not valid:
                return "process-envelope-invalid", "process_envelope"

        raw_labels = _ticket_field(ticket, "labels") or []
        labels = [str(lbl).strip().lower() for lbl in raw_labels]
        if "blocked" in labels:
            return "label:blocked", "blocked"
        if "autonomy-frontier" in labels:
            return "autonomy-frontier", "autonomy_blocked"
        if "actor:human" in labels:
            return "actor:human", "human_owned"
        for lbl in labels:
            if lbl.startswith("waiting:"):
                return lbl, "waiting"
            if lbl.startswith("needs-human"):
                return lbl, "human_owned"

    goal = (os.environ.get("CURRENT_GOAL") or "").strip()
    if goal:
        domain = goal.split(".")[0].lower()
        raw_labels = _ticket_field(ticket, "labels") or []
        labels = [str(lbl).strip().lower() for lbl in raw_labels]
        if f"goal:{goal.lower()}" not in labels and f"goal:{domain}" not in labels:
            name = str(_ticket_field(ticket, "name", "") or "")
            desc = str(_ticket_field(ticket, "description", "") or "")
            blob = f"{name} {desc} {' '.join(labels)}".lower()
            if domain not in blob:
                return "goal-frozen", "goal_frozen"

    return "", ""


def _resolve_dependency_status(
    dep_id: str,
    *,
    pf: Planfile | None,
    ticket_by_id: Mapping[str, Ticket | Mapping[str, Any]] | None,
) -> str | None:
    if ticket_by_id is not None and dep_id in ticket_by_id:
        dep = ticket_by_id[dep_id]
        return _normalize_status(_ticket_field(dep, "status"))
    if pf is not None:
        dep_ticket = pf.get_ticket(dep_id)
        if dep_ticket is not None:
            return _normalize_status(dep_ticket.status)
    return None


def evaluate_executable_candidate(
    ticket: Ticket | Mapping[str, Any],
    *,
    pf: Planfile | None = None,
    ticket_by_id: Mapping[str, Ticket | Mapping[str, Any]] | None = None,
    repo_path: str | Path | None = None,
    workspace_root: str | Path | None = None,
    queue: str | None = None,
    now: datetime | None = None,
    observations: MutableMapping[Path, TargetRepoObservation] | None = None,
    slug_index: SlugIndex | None = None,
) -> CandidateEvaluation:
    """Evaluate whether ``ticket`` belongs to the canonical executable pending queue."""

    sprint = str(_ticket_field(ticket, "sprint", "current") or "current").strip()
    if sprint.startswith(("history-", "archive-")):
        return CandidateEvaluation(
            executable=False,
            reason="archived_sprint",
            category="archived",
        )

    status = _normalize_status(_ticket_field(ticket, "status"))
    if status != "open":
        return CandidateEvaluation(
            executable=False,
            reason=f"status:{status or 'unknown'}",
            category=f"status_{status or 'unknown'}",
        )

    exec_state, ticket_queue = _extract_exec_state_and_queue(ticket)
    if exec_state not in RUNNABLE_EXECUTION_STATES:
        return CandidateEvaluation(
            executable=False,
            reason=f"exec_state:{exec_state}",
            category="exec_state",
        )

    if queue is not None and ticket_queue != queue:
        return CandidateEvaluation(
            executable=False,
            reason=f"queue:{ticket_queue}",
            category="queue_mismatch",
        )

    autonomy_reason, autonomy_category = _check_autonomy_and_goal(ticket)
    if autonomy_reason:
        return CandidateEvaluation(
            executable=False,
            reason=autonomy_reason,
            category=autonomy_category,
        )

    blocked_by = _ticket_field(ticket, "blocked_by") or []
    for raw_dep in blocked_by:
        dep_id = str(raw_dep or "").strip()
        if not dep_id:
            continue
        dep_status = _resolve_dependency_status(
            dep_id,
            pf=pf,
            ticket_by_id=ticket_by_id,
        )
        if dep_status is None or dep_status not in SATISFIED_DEPENDENCY_STATUSES:
            return CandidateEvaluation(
                executable=False,
                reason=f"blocked_by:{dep_id}",
                category="dependency_unresolved",
            )

    current_time = _utc_now(now)
    default_repo = (
        Path(repo_path)
        if repo_path is not None
        else (pf.store.primary_project_dir if pf is not None else None)
    )
    ws_root = Path(workspace_root) if workspace_root is not None else None
    obs_cache: MutableMapping[Path, TargetRepoObservation] = (
        observations if observations is not None else {}
    )

    obs, unobserved_reason = resolve_ticket_target_repo(
        ticket,
        default_repo_dir=default_repo,
        workspace_root=ws_root,
        now=current_time,
        observations=obs_cache,
        slug_index=slug_index,
    )
    if obs is None or unobserved_reason is not None:
        return CandidateEvaluation(
            executable=False,
            reason=unobserved_reason or "target_repository_invalid",
            category="invalid_target_repository",
        )

    live_status = find_live_ticket_binding(ticket, obs, now=current_time)
    if live_status.ambiguous_error is not None:
        return CandidateEvaluation(
            executable=False,
            reason=live_status.ambiguous_error,
            category="ambiguous_lease_state",
            repo_path=str(obs.repo_dir),
            repository=obs.repository_slug,
        )
    if live_status.is_live:
        return CandidateEvaluation(
            executable=False,
            reason=live_status.reason,
            category="active_lease",
            repo_path=str(obs.repo_dir),
            repository=obs.repository_slug,
        )

    return CandidateEvaluation(
        executable=True,
        reason="",
        category="executable",
        repo_path=str(obs.repo_dir),
        repository=obs.repository_slug,
    )


def is_executable_candidate(
    ticket: Ticket | Mapping[str, Any],
    *,
    pf: Planfile | None = None,
    ticket_by_id: Mapping[str, Ticket | Mapping[str, Any]] | None = None,
    repo_path: str | Path | None = None,
    workspace_root: str | Path | None = None,
    queue: str | None = None,
    now: datetime | None = None,
    observations: MutableMapping[Path, TargetRepoObservation] | None = None,
) -> bool:
    """Return ``True`` iff ``ticket`` satisfies the canonical executable pending queue contract."""

    return evaluate_executable_candidate(
        ticket,
        pf=pf,
        ticket_by_id=ticket_by_id,
        repo_path=repo_path,
        workspace_root=workspace_root,
        queue=queue,
        now=now,
        observations=observations,
    ).executable


def executable_skip_reason(
    ticket: Ticket | Mapping[str, Any],
    *,
    pf: Planfile | None = None,
    ticket_by_id: Mapping[str, Ticket | Mapping[str, Any]] | None = None,
    repo_path: str | Path | None = None,
    workspace_root: str | Path | None = None,
    queue: str | None = None,
    now: datetime | None = None,
    observations: MutableMapping[Path, TargetRepoObservation] | None = None,
) -> str:
    """Return ``''`` when ``ticket`` is executable, else its canonical skip reason."""

    return evaluate_executable_candidate(
        ticket,
        pf=pf,
        ticket_by_id=ticket_by_id,
        repo_path=repo_path,
        workspace_root=workspace_root,
        queue=queue,
        now=now,
        observations=observations,
    ).reason


def _candidate_sort_key(
    item: tuple[Ticket, CandidateEvaluation],
) -> tuple[int, int, str, str]:
    ticket = item[0]
    labels = [str(lbl).lower() for lbl in (ticket.labels or [])]
    is_bug = 0 if "bug" in labels else 1
    priority_str = str(ticket.priority or "normal").strip().lower()
    created_str = (
        ticket.created_at.isoformat()
        if isinstance(ticket.created_at, datetime)
        else str(ticket.created_at or "")
    )
    return (_PRIORITY_ORDER.get(priority_str, 99), is_bug, created_str, ticket.id)


def executable_queue(
    pf_or_path: Planfile | str | Path = ".",
    *,
    sprint: str = "active",
    workspace_root: str | Path | None = None,
    queue: str | None = None,
    now: datetime | None = None,
    observations: MutableMapping[Path, TargetRepoObservation] | None = None,
) -> dict[str, Any]:
    """Compute the canonical ``planfile.executable-queue/v1`` summary for one repository."""

    from planfile import Planfile as PlanfileCls

    pf = (
        pf_or_path
        if isinstance(pf_or_path, PlanfileCls)
        else PlanfileCls(str(pf_or_path))
    )
    current_time = _utc_now(now)
    now_iso = current_time.isoformat().replace("+00:00", "Z")
    default_repo = pf.store.primary_project_dir
    ws_root = Path(workspace_root) if workspace_root is not None else None
    obs_cache: MutableMapping[Path, TargetRepoObservation] = (
        observations if observations is not None else {}
    )
    slug_index = _deferred_slug_index(ws_root, obs_cache, current_time)

    tickets = iter_sprint_tickets(pf, sprint=sprint)
    ticket_by_id = pf._ticket_snapshot_with_dependencies(tickets)

    status_counts: dict[str, int] = {
        "open": 0,
        "in_progress": 0,
        "blocked": 0,
        "done": 0,
        "canceled": 0,
        "failed": 0,
        "review": 0,
    }
    excluded_by_reason: dict[str, int] = {}
    executable_pairs: list[tuple[Ticket, CandidateEvaluation]] = []
    skipped_items: list[ExecutableSkippedItemV1] = []

    for ticket in tickets:
        norm_status = _normalize_status(ticket.status)
        if norm_status in status_counts:
            status_counts[norm_status] += 1

        evaluation = evaluate_executable_candidate(
            ticket,
            pf=pf,
            ticket_by_id=ticket_by_id,
            repo_path=default_repo,
            workspace_root=ws_root,
            queue=queue,
            now=current_time,
            observations=obs_cache,
            slug_index=slug_index,
        )
        if evaluation.executable:
            executable_pairs.append((ticket, evaluation))
        else:
            excluded_by_reason[evaluation.category] = (
                excluded_by_reason.get(evaluation.category, 0) + 1
            )
            skipped_items.append(
                ExecutableSkippedItemV1(
                    id=ticket.id,
                    status=norm_status or "unknown",
                    sprint=ticket.sprint or "current",
                    reason=evaluation.reason,
                    category=evaluation.category,
                    repository=evaluation.repository,
                )
            )

    executable_pairs.sort(key=_candidate_sort_key)
    candidate_models: list[ExecutableCandidateV1] = []
    for ticket, evaluation in executable_pairs:
        _, ticket_queue = _extract_exec_state_and_queue(ticket)
        created_iso = (
            ticket.created_at.isoformat()
            if isinstance(ticket.created_at, datetime)
            else (str(ticket.created_at) if ticket.created_at else None)
        )
        candidate_models.append(
            ExecutableCandidateV1(
                id=ticket.id,
                name=ticket.name,
                priority=str(ticket.priority or "normal"),
                sprint=ticket.sprint or "current",
                queue=ticket_queue,
                repository=evaluation.repository,
                repo_path=evaluation.repo_path or str(default_repo),
                labels=list(ticket.labels or []),
                files=list(ticket.files or []),
                blocked_by=list(ticket.blocked_by or []),
                created_at=created_iso,
            )
        )

    default_obs = obs_cache.get(default_repo.resolve()) if default_repo.exists() else None
    summary = ExecutableQueueSummaryV1(
        generated_at=now_iso,
        project_dir=str(default_repo),
        repository=default_obs.repository_slug if default_obs else None,
        sprint=sprint,
        queue=queue,
        counts=ExecutableQueueCountsV1(
            total_scanned=len(tickets),
            open=status_counts["open"],
            in_progress=status_counts["in_progress"],
            blocked=status_counts["blocked"],
            done=status_counts["done"],
            canceled=status_counts["canceled"],
            failed=status_counts["failed"],
            review=status_counts["review"],
            executable=len(candidate_models),
            excluded=len(skipped_items),
        ),
        excluded_by_reason=dict(sorted(excluded_by_reason.items())),
        candidate_ids=[cand.id for cand in candidate_models],
        candidates=candidate_models,
        skipped=skipped_items,
    )
    return summary.model_dump(mode="json", by_alias=True)


def fleet_executable_queue(
    workspace_root: str | Path,
    *,
    sprint: str = "active",
    queue: str | None = None,
    now: datetime | None = None,
    max_depth: int = 2,
) -> dict[str, Any]:
    """Compute a unified ``planfile.executable-queue/v1`` report across all fleet repositories."""

    current_time = _utc_now(now)
    now_iso = current_time.isoformat().replace("+00:00", "Z")
    ws_path = Path(workspace_root)
    obs_cache: dict[Path, TargetRepoObservation] = {}
    repos = discover_planfile_repositories(ws_path, max_depth=max_depth)

    totals = {
        "total_scanned": 0,
        "open": 0,
        "in_progress": 0,
        "blocked": 0,
        "done": 0,
        "canceled": 0,
        "failed": 0,
        "review": 0,
        "executable": 0,
        "excluded": 0,
    }
    excluded_by_reason: dict[str, int] = {}
    all_candidates: list[dict[str, Any]] = []
    all_skipped: list[dict[str, Any]] = []
    repo_summaries: list[dict[str, Any]] = []

    for repo_dir in repos:
        repo_report = executable_queue(
            repo_dir,
            sprint=sprint,
            workspace_root=ws_path,
            queue=queue,
            now=current_time,
            observations=obs_cache,
        )
        repo_summaries.append(
            {
                "project_dir": repo_report["project_dir"],
                "repository": repo_report["repository"],
                "counts": repo_report["counts"],
                "candidate_ids": repo_report["candidate_ids"],
            }
        )
        for key in totals:
            totals[key] += int(repo_report["counts"][key])
        for reason_key, count in repo_report["excluded_by_reason"].items():
            excluded_by_reason[reason_key] = (
                excluded_by_reason.get(reason_key, 0) + int(count)
            )
        all_candidates.extend(repo_report["candidates"])
        all_skipped.extend(repo_report["skipped"])

    all_candidates.sort(
        key=lambda c: (
            _PRIORITY_ORDER.get(str(c.get("priority") or "normal").lower(), 99),
            0 if "bug" in [str(x).lower() for x in (c.get("labels") or [])] else 1,
            str(c.get("created_at") or ""),
            str(c.get("repository") or ""),
            str(c.get("id") or ""),
        )
    )
    return {
        "schema": EXECUTABLE_QUEUE_SCHEMA,
        "generated_at": now_iso,
        "workspace_root": str(ws_path),
        "sprint": sprint,
        "queue": queue,
        "repositories_scanned": len(repos),
        "counts": totals,
        "excluded_by_reason": dict(sorted(excluded_by_reason.items())),
        "candidate_ids": [str(c["id"]) for c in all_candidates],
        "candidates": all_candidates,
        "skipped": all_skipped,
        "repositories": repo_summaries,
    }


__all__ = [
    "EXECUTABLE_QUEUE_SCHEMA",
    "RUNNABLE_EXECUTION_STATES",
    "SATISFIED_DEPENDENCY_STATUSES",
    "CandidateEvaluation",
    "evaluate_executable_candidate",
    "executable_queue",
    "executable_skip_reason",
    "fleet_executable_queue",
    "is_executable_candidate",
]


class _CallableExecutableQueueModule(types.ModuleType):
    def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return executable_queue(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableExecutableQueueModule
