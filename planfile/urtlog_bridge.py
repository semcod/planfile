"""Optional, fail-open uritime-urtlog bridge for Planfile ticket lifecycle and DAGs.

Activated strictly when ``URTLOG_STATE_DIR`` is set and ``urtlog`` is importable.
Zero mandatory runtime dependencies.

Projects Planfile CLI ticket mutations (``create``, ``depend``, ``update``,
``block``, ``done``, ``start``, ``claim``, ``ready``, ``resume``, ``fail``,
``input``, ``complete``) into ``UrtLogStore`` (PLAN/LOG records with DAG
``causation_id`` / ``depends_on`` edges) and indexes each ticket URN
(``urn:planfile:ticket:<id>``) in ``UnifiedRegistry`` so Heyasa / Liquid D1
decision models can observe completed, blocked, and queued work.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib
import os
from pathlib import Path
from typing import Any, Sequence


def resolve_state_dir(explicit: Path | str | None = None) -> Path | None:
    """Return configured urtlog state directory, or None when opt-in is inactive."""
    raw = str(explicit).strip() if explicit is not None else os.environ.get("URTLOG_STATE_DIR", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _load_urtlog() -> Any | None:
    try:
        return importlib.import_module("urtlog")
    except (ImportError, OSError, AttributeError, RuntimeError):
        return None


def _now_us() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000)


def _slug(value: str, fallback: str = "unknown") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(value).strip()).strip("-")
    return cleaned or fallback


def _ticket_urn(ticket_id: str) -> str:
    return f"urn:planfile:ticket:{_slug(ticket_id)}"


def _extract_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _norm_enum(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def maybe_emit_ticket_created(
    ticket: Any,
    *,
    created: bool = True,
    repository: str = "semcod/planfile",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Emit a Planfile ticket create/reuse intent into UrtLogStore and register its URN."""
    target_dir = resolve_state_dir(state_dir)
    if target_dir is None:
        return {"emitted": False, "reason": "disabled"}
    urtlog_mod = _load_urtlog()
    if urtlog_mod is None:
        return {"emitted": False, "reason": "urtlog_not_installed"}

    tid = str(_extract_attr(ticket, "id", "unknown"))
    title = str(_extract_attr(ticket, "name", "") or "")
    sprint = str(_extract_attr(ticket, "sprint", "current") or "current")
    priority = _norm_enum(_extract_attr(ticket, "priority", "normal"), "normal")
    status_val = _norm_enum(_extract_attr(ticket, "status", "open"), "open")
    labels = list(_extract_attr(ticket, "labels", []) or [])
    blocked_by = list(_extract_attr(ticket, "blocked_by", []) or [])
    at_us = _now_us()
    event_id = f"plf-create-{_slug(tid)}-{at_us}"
    op_uri = f"planfile://ticket/{'create' if created else 'reuse'}/{_slug(tid)}"
    urn = _ticket_urn(tid)

    try:
        with urtlog_mod.UrtClient(target_dir, source="planfile", repository=repository) as client:
            client.registry.register_urn(
                urn,
                owner="semcod/planfile",
                system="planfile",
                description=f"[{status_val}|{priority}|sprint:{sprint}] {title[:180]}",
                sensitivity="internal",
                revision=status_val,
                metadata={
                    "ticket_id": tid,
                    "title": title[:240],
                    "status": status_val,
                    "priority": priority,
                    "sprint": sprint,
                    "labels": labels[:12],
                    "blocked_by": blocked_by[:20],
                },
            )
            record = urtlog_mod.UrtEventRecord(
                event_id=event_id,
                kind="intent",
                source="planfile",
                urt=urtlog_mod.UrtTime(at_us=at_us),
                uri=urtlog_mod.OperationUri.parse(op_uri),
                inputs=(
                    urtlog_mod.DataRef(
                        urn=f"urn:planfile:sprint:{_slug(sprint)}",
                        role="sprint",
                        sensitivity="internal",
                    ),
                ),
                outputs=(
                    urtlog_mod.DataRef(
                        urn=urn,
                        role="ticket",
                        sensitivity="internal",
                    ),
                ),
                status="planned",
                repository=repository,
                actor="planfile",
                sensitivity="internal",
                owner_principal="planfile",
                run_id=f"planfile-{_slug(tid)}",
                log_type="lifecycle",
                summary=f"{'Created' if created else 'Reused'} {tid} ({priority}, {sprint}): {title[:140]}",
                metadata={
                    "ticket_id": tid,
                    "created": bool(created),
                    "title": title[:240],
                    "priority": priority,
                    "sprint": sprint,
                    "status": status_val,
                    "labels": labels[:12],
                    "depends_on": blocked_by[:20],
                },
                custody=urtlog_mod.Custody(
                    commissioned_by="planfile",
                    executed_by="planfile",
                    recipients=("group:ops", "heyasa"),
                ),
            )
            client.store.append(record)
        return {"emitted": True, "event_id": event_id, "uri": op_uri, "urn": urn}
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError, KeyError):
        return {"emitted": False, "reason": "emit_failed"}


def maybe_emit_ticket_dependency(
    ticket_id: str,
    *,
    after: Sequence[str] = (),
    before: Sequence[str] = (),
    repository: str = "semcod/planfile",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Emit a Planfile DAG dependency edge (`--after`/`--before`) into UrtLogStore."""
    target_dir = resolve_state_dir(state_dir)
    if target_dir is None:
        return {"emitted": False, "reason": "disabled"}
    urtlog_mod = _load_urtlog()
    if urtlog_mod is None:
        return {"emitted": False, "reason": "urtlog_not_installed"}

    after_list = [str(x) for x in after if x]
    before_list = [str(x) for x in before if x]
    at_us = _now_us()
    event_id = f"plf-depend-{_slug(ticket_id)}-{at_us}"
    op_uri = f"planfile://ticket/depend/{_slug(ticket_id)}"
    urn = _ticket_urn(ticket_id)

    inputs = tuple(
        urtlog_mod.DataRef(urn=_ticket_urn(dep), role="dependency", sensitivity="internal")
        for dep in after_list
    ) or (urtlog_mod.DataRef(urn=urn, role="ticket", sensitivity="internal"),)
    outputs = (
        urtlog_mod.DataRef(urn=urn, role="dependent_ticket", sensitivity="internal"),
        *(
            urtlog_mod.DataRef(urn=_ticket_urn(nxt), role="downstream_ticket", sensitivity="internal")
            for nxt in before_list
        ),
    )

    parts = []
    if after_list:
        parts.append(f"after {', '.join(after_list)}")
    if before_list:
        parts.append(f"before {', '.join(before_list)}")
    summary = f"Sequenced {ticket_id}: {'; '.join(parts) or 'dependency updated'}"

    try:
        with urtlog_mod.UrtClient(target_dir, source="planfile", repository=repository) as client:
            client.registry.register_urn(
                urn,
                owner="semcod/planfile",
                system="planfile",
                description=f"[waiting_dependency] {summary[:180]}",
                sensitivity="internal",
                revision="sequenced",
                metadata={
                    "ticket_id": ticket_id,
                    "status": "waiting_dependency" if after_list else "open",
                    "depends_on": after_list,
                    "blocks": before_list,
                },
            )
            record = urtlog_mod.UrtEventRecord(
                event_id=event_id,
                kind="intent",
                source="planfile",
                urt=urtlog_mod.UrtTime(at_us=at_us),
                uri=urtlog_mod.OperationUri.parse(op_uri),
                inputs=inputs,
                outputs=outputs,
                status="planned",
                repository=repository,
                actor="planfile",
                sensitivity="internal",
                owner_principal="planfile",
                run_id=f"planfile-{_slug(ticket_id)}",
                causation_id=f"planfile-{_slug(after_list[0])}" if after_list else None,
                log_type="lifecycle",
                summary=summary[:240],
                metadata={
                    "ticket_id": ticket_id,
                    "depends_on": after_list,
                    "blocks": before_list,
                },
                custody=urtlog_mod.Custody(
                    commissioned_by="planfile",
                    executed_by="planfile",
                    recipients=("group:ops", "heyasa"),
                ),
            )
            client.store.append(record)
        return {"emitted": True, "event_id": event_id, "uri": op_uri, "depends_on": after_list}
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError, KeyError):
        return {"emitted": False, "reason": "emit_failed"}


def maybe_emit_ticket_event(
    action: str,
    ticket: Any,
    *,
    reason: str | None = None,
    note: str | None = None,
    repository: str = "semcod/planfile",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Emit a Planfile ticket transition (`update`, `block`, `done`, `fail`, `start`, `ready`, etc.)."""
    target_dir = resolve_state_dir(state_dir)
    if target_dir is None:
        return {"emitted": False, "reason": "disabled"}
    urtlog_mod = _load_urtlog()
    if urtlog_mod is None:
        return {"emitted": False, "reason": "urtlog_not_installed"}

    tid = str(_extract_attr(ticket, "id", str(ticket)))
    title = str(_extract_attr(ticket, "name", "") or "")
    status_val = _norm_enum(_extract_attr(ticket, "status", action), action)
    priority = _norm_enum(_extract_attr(ticket, "priority", "normal"), "normal")
    sprint = str(_extract_attr(ticket, "sprint", "current") or "current")
    blocked_by = list(_extract_attr(ticket, "blocked_by", []) or [])
    clean_action = _slug(action, "update").lower()

    if clean_action in {"block", "input"}:
        urt_status = "unknown"
        log_type = "audit"
    elif clean_action == "fail":
        urt_status = "failed"
        log_type = "error"
    elif clean_action in {"done", "complete"}:
        urt_status = "succeeded"
        log_type = "summary"
    else:
        urt_status = "succeeded"
        log_type = "lifecycle"

    detail = reason or note or title
    summary = f"Ticket {tid} {clean_action} ({status_val})" + (f": {str(detail)[:160]}" if detail else "")
    at_us = _now_us()
    event_id = f"plf-{clean_action}-{_slug(tid)}-{at_us}"
    op_uri = f"planfile://ticket/{clean_action}/{_slug(tid)}"
    urn = _ticket_urn(tid)

    try:
        with urtlog_mod.UrtClient(target_dir, source="planfile", repository=repository) as client:
            client.registry.register_urn(
                urn,
                owner="semcod/planfile",
                system="planfile",
                description=f"[{status_val}|{priority}] {title[:120]}" + (f" | {str(reason or note)[:100]}" if (reason or note) else ""),
                sensitivity="internal",
                revision=status_val,
                metadata={
                    "ticket_id": tid,
                    "title": title[:240],
                    "status": status_val,
                    "action": clean_action,
                    "priority": priority,
                    "sprint": sprint,
                    "blocked_by": blocked_by[:20],
                    "reason": reason[:300] if reason else None,
                    "note": note[:300] if note else None,
                },
            )
            record = urtlog_mod.UrtEventRecord(
                event_id=event_id,
                kind="log",
                source="planfile",
                urt=urtlog_mod.UrtTime(at_us=at_us),
                uri=urtlog_mod.OperationUri.parse(op_uri),
                inputs=(
                    urtlog_mod.DataRef(urn=urn, role="ticket", sensitivity="internal"),
                ),
                outputs=(
                    urtlog_mod.DataRef(
                        urn=f"{urn}:state:{_slug(status_val)}",
                        role="ticket_state",
                        sensitivity="internal",
                    ),
                ),
                status=urt_status,
                repository=repository,
                actor="planfile",
                sensitivity="internal",
                owner_principal="planfile",
                run_id=f"planfile-{_slug(tid)}",
                stage="completed",
                log_type=log_type,
                summary=summary[:240],
                metadata={
                    "ticket_id": tid,
                    "action": clean_action,
                    "status": status_val,
                    "priority": priority,
                    "sprint": sprint,
                    "blocked_by": blocked_by[:20],
                    "reason": reason[:400] if reason else None,
                    "note": note[:400] if note else None,
                },
                custody=urtlog_mod.Custody(
                    commissioned_by="planfile",
                    executed_by="planfile",
                    recipients=("group:ops", "heyasa"),
                ),
            )
            client.store.append(record)
        return {"emitted": True, "event_id": event_id, "uri": op_uri, "status": urt_status}
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError, KeyError):
        return {"emitted": False, "reason": "emit_failed"}


def load_planfile_queue_brief(
    *,
    limit: int = 50,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Read compact Planfile ticket/DAG state from UnifiedRegistry + UrtLogStore for Heyasa/D1."""
    target_dir = resolve_state_dir(state_dir)
    if target_dir is None:
        return {"enabled": False, "reason": "disabled", "tickets": [], "blocked": [], "done": [], "queued": []}
    urtlog_mod = _load_urtlog()
    if urtlog_mod is None:
        return {"enabled": False, "reason": "urtlog_not_installed", "tickets": [], "blocked": [], "done": [], "queued": []}

    ctx = urtlog_mod.AccessContext(
        "heyasa",
        roles=frozenset({"assistant"}),
        groups=frozenset({"ops"}),
        max_sensitivity="internal",
    )
    try:
        with urtlog_mod.UrtClient(target_dir, source="planfile", repository="semcod/planfile") as client:
            urn_rows = client.registry.search(ctx, kind="urn", system="planfile", limit=max(1, min(int(limit), 200)))
            events = client.store.query(ctx, source="planfile", op_prefix="op/planfile/ticket/", limit=max(1, min(int(limit) * 2, 200)))

        tickets: list[dict[str, Any]] = []
        blocked: list[str] = []
        done: list[str] = []
        queued: list[str] = []
        for row in urn_rows:
            meta = row.get("metadata") or {}
            tid = str(meta.get("ticket_id") or row.get("address", ""))
            st = str(meta.get("status") or row.get("revision") or "unknown").lower()
            entry = {
                "ticket_id": tid,
                "urn": row.get("address"),
                "status": st,
                "description": row.get("description", ""),
                "depends_on": meta.get("depends_on") or meta.get("blocked_by") or [],
                "reason": meta.get("reason"),
                "note": meta.get("note"),
            }
            tickets.append(entry)
            if st == "blocked":
                blocked.append(tid)
            elif st in {"done", "completed"}:
                done.append(tid)
            else:
                queued.append(tid)

        return {
            "enabled": True,
            "ticket_count": len(tickets),
            "event_count": len(events),
            "done": done,
            "blocked": blocked,
            "queued": queued,
            "tickets": tickets,
        }
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError, KeyError):
        return {"enabled": False, "reason": "query_failed", "tickets": [], "blocked": [], "done": [], "queued": []}
