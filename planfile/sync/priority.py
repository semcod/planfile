"""Canonical inbound evidence and selected, local-only legacy priority repair."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import yaml

from planfile.core.models import Ticket

_LABEL = re.compile(r"^priority\s*(?:::|:|-)\s*(.*)$", re.IGNORECASE)
_CANONICAL = {"critical", "high", "normal", "low"}
_ALIASES = {"medium": "normal", "med": "normal"}


def normalize_inbound_priority(data: dict[str, Any]) -> str:
    """Resolve all supplied evidence; absence alone selects the model default.

    Explicit null/empty/unknown values are errors, as are contradictory labels
    or an explicit value that disagrees with a label. Never resolve by order.
    """
    identity = data.get("id", "<unknown>")
    evidence: list[tuple[str, Any]] = []
    if "priority" in data:
        evidence.append(("priority", data["priority"]))
    labels = data.get("labels")
    if labels is not None:
        if not isinstance(labels, (list, tuple)):
            raise ValueError(f"inbound_priority_invalid: ticket {identity}: labels={labels!r}")
        for label in labels:
            if not isinstance(label, str):
                raise ValueError(f"inbound_priority_invalid: ticket {identity}: label={label!r}")
            match = _LABEL.fullmatch(label.strip())
            if match:
                evidence.append((f"label {label!r}", match.group(1)))
            elif label.strip().lower() == "priority":
                evidence.append((f"label {label!r}", ""))
    values = set()
    for source, value in evidence:
        normalized = value.strip().lower() if isinstance(value, str) else None
        normalized = _ALIASES.get(normalized, normalized)
        if normalized not in _CANONICAL:
            raise ValueError(
                f"inbound_priority_invalid: ticket {identity}: {source}={value!r}; "
                "expected critical, high, normal or low (medium/med alias normal)"
            )
        values.add(normalized)
    if len(values) > 1:
        raise ValueError(f"inbound_priority_conflict: ticket {identity}: evidence={evidence!r}")
    return next(iter(values)) if values else Ticket.model_fields["priority"].default


@dataclass(frozen=True)
class PriorityRepairItem:
    ticket_id: str
    sprint: str | None
    evidence: dict[str, Any]
    priority: str | None
    diagnostic: str | None = None
    expected_snapshot: dict[str, Any] | None = field(default=None, repr=False)


@dataclass(frozen=True)
class PriorityRepairPlan:
    project_dir: str
    items: tuple[PriorityRepairItem, ...]


def _selected_raw_records(store, ticket_ids):
    records = {ticket_id: [] for ticket_id in ticket_ids}
    for sprint in store._all_sprint_ids():
        paths = (
            {store._sharded_storage().shard_path(sprint, ticket_id) for ticket_id in ticket_ids}
            if store._uses_sharded_storage()
            else {store._sprint_file(sprint)}
        )
        for path in paths:
            if not path.exists():
                continue
            # Plain YAML reads deliberately avoid index/mirror repair side effects.
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            section = data.get("sprint", data)
            for ticket_id, raw in (section.get("tickets") or {}).items():
                if ticket_id in records:
                    records[ticket_id].append((str(sprint), deepcopy(raw)))
    return records


def preview_priority_repair(store, ticket_ids: list[str]) -> PriorityRepairPlan:
    """Read raw records for explicit IDs, without writes or default-filled reads.

    Present priorities are left untouched. Diagnostics prevent application of
    the whole selection; the operator can then preview a narrower selection.
    """
    if (
        not isinstance(ticket_ids, (list, tuple))
        or not ticket_ids
        or any(not isinstance(value, str) or not value.strip() for value in ticket_ids)
    ):
        raise ValueError("priority_repair_selection_required")
    selected = list(dict.fromkeys(ticket_ids))
    records = _selected_raw_records(store, selected)
    items = []
    for ticket_id in selected:
        matches = records[ticket_id]
        if len(matches) != 1:
            items.append(
                PriorityRepairItem(
                    ticket_id,
                    None,
                    {},
                    None,
                    f"priority_repair_identity_invalid: {ticket_id}: matches={len(matches)}",
                )
            )
            continue
        sprint, raw = matches[0]
        if not isinstance(raw, dict):
            items.append(
                PriorityRepairItem(
                    ticket_id, sprint, {}, None, f"priority_repair_record_invalid: {ticket_id}"
                )
            )
            continue
        evidence = {key: deepcopy(raw[key]) for key in ("priority", "labels") if key in raw}
        if "priority" in raw:
            items.append(PriorityRepairItem(ticket_id, sprint, evidence, None))
            continue
        refs = raw.get("sync") or {}
        imported = bool(raw.get("external_id") and raw.get("backend")) or any(
            isinstance(ref, dict) and ref.get("id")
            for ref in (refs.values() if isinstance(refs, dict) else [])
        )
        try:
            if not imported:
                raise ValueError(f"priority_repair_not_imported: {ticket_id}")
            # Validate before mutation; defaulted fields are never the repair input.
            Ticket.model_validate({**raw, "priority": "normal"})
            priority = normalize_inbound_priority({**evidence, "id": ticket_id})
            items.append(
                PriorityRepairItem(ticket_id, sprint, evidence, priority, expected_snapshot=raw)
            )
        except ValueError as exc:
            items.append(PriorityRepairItem(ticket_id, sprint, evidence, None, str(exc)))
    return PriorityRepairPlan(str(store.project_dir.resolve()), tuple(items))


def apply_priority_repair(store, plan: PriorityRepairPlan, *, actor: str, reason: str) -> list[str]:
    """Apply only previewed missing fields through the ordinary locked/CAS SDK.

    This function invokes no backend or completion worker. Store audit and
    local enqueue policy remain intact; a repaired backlog is not execution.
    Re-previewing repaired records yields a no-op plan.
    """
    if plan.project_dir != str(store.project_dir.resolve()):
        raise ValueError("priority_repair_project_mismatch")
    if not actor.strip() or not reason.strip():
        raise ValueError("priority_repair_audit_required")
    if any(item.diagnostic for item in plan.items):
        raise ValueError(
            "priority_repair_diagnostics: "
            + "; ".join(item.diagnostic for item in plan.items if item.diagnostic)
        )
    applied = []
    for item in plan.items:
        if item.priority is None:
            continue
        snapshot = deepcopy(item.expected_snapshot)
        if (
            not isinstance(snapshot, dict)
            or "priority" in snapshot
            or (normalize_inbound_priority({**snapshot, "id": item.ticket_id}) != item.priority)
        ):
            raise ValueError(f"priority_repair_plan_invalid: {item.ticket_id}")
        updated = store.update_ticket(
            item.ticket_id,
            expected_snapshot=snapshot,
            priority=item.priority,
            actor=actor,
            reason=reason,
        )
        if updated is None:
            raise ValueError(f"priority_repair_ticket_disappeared: {item.ticket_id}")
        applied.append(item.ticket_id)
    return applied
