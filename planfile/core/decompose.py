"""Git-like task decomposition for planfile.

A big assignment is often several smaller pieces. Just as git lets you split a commit,
refactor history, and keep changes on disjoint files so they never conflict, this module
lets ONE agent break a ticket into subtasks it owns and orchestrates:

  * ``split_ticket`` — decompose a parent into child subtasks (single owner, file-scoped so
    they don't collide), with the parent rolled up as an epic ``blocked_by`` its children.
  * ``group_tickets`` — gather related tickets under a named group (epic label).
  * ``build_tree`` — inspect the decomposition as a nested parent→children tree.
  * ``merge_ticket`` — refactor: fold a subtask back into another ticket (git squash-like).

All functions operate on a live ``Planfile`` instance and reuse its create/update API, so the
mutation lock, history, and sync stay intact. They are pure orchestration over the store.
"""
from __future__ import annotations

from typing import Any


class DecomposeError(ValueError):
    """Raised when a decomposition request is invalid (missing parent, no subtasks, …)."""


def _normalize_subtask(subtask: Any) -> dict:
    """Accept a plain name string or a ``{name, description?, files?, labels?}`` dict."""
    if isinstance(subtask, str):
        name = subtask.strip()
        if not name:
            raise DecomposeError("empty subtask name")
        return {"name": name}
    if isinstance(subtask, dict) and str(subtask.get("name") or "").strip():
        return dict(subtask)
    raise DecomposeError(f"invalid subtask (need name): {subtask!r}")


def _dedup(seq: list[str]) -> list[str]:
    return list(dict.fromkeys(x for x in seq if x))


def _child_data(parent: Any, parent_id: str, sub: dict, index: int,
                priority: str | None, sprint: str | None, executor: Any,
                agent_labels: list[str], source: str) -> dict:
    """Assemble the create-kwargs for one subtask: inherit parent priority/sprint/labels,
    tag ``parent:<id>`` (+ agent), carry optional file scope + single-owner executor."""
    from planfile import TicketSource
    labels = _dedup([*(parent.labels or []), f"parent:{parent_id}", *agent_labels, *(sub.get("labels") or [])])
    data: dict[str, Any] = {
        "priority": priority or parent.priority,
        "sprint": sprint or parent.sprint,
        "source": TicketSource(tool=source, context={"parent": parent_id, "index": index}),
        "labels": labels,
        "description": sub.get("description", ""),
        "parent": parent_id,
    }
    if sub.get("files"):
        data["files"] = list(sub["files"])
    if executor is not None:
        data["executor"] = executor
    return data


def split_ticket(
    pf: Any,
    parent_id: str,
    subtasks: list[Any],
    *,
    assignee: str | None = None,
    priority: str | None = None,
    sprint: str | None = None,
    block_parent: bool = True,
    sequential: bool = False,
    source: str = "decompose",
) -> list[Any]:
    """Break ``parent_id`` into child subtasks (git-like commit split).

    Each child inherits the parent's priority/sprint/labels, is tagged ``parent:<id>`` and,
    when ``assignee`` is given, ``agent:<assignee>`` — so the whole decomposition is
    single-owner and non-conflicting. Optional per-child ``files`` scope keeps subtasks on
    disjoint files. With ``block_parent`` the parent becomes ``blocked_by`` all children, so
    the epic only completes once every subtask is done.

    With ``sequential`` the children are STACKED (git-stacked-branches style): child *i* is
    ``blocked_by`` child *i-1*, so one agent runs them strictly in order — the runnable front
    is always a single subtask, which is how you orchestrate dependent steps without conflict.
    Returns the created child Tickets (in order).
    """
    from planfile import TicketExecutor, TicketSource  # local import: avoid cycle at module load

    parent = pf.get_ticket(parent_id)
    if not parent:
        raise DecomposeError(f"parent ticket {parent_id} not found")
    norm = [_normalize_subtask(s) for s in subtasks]
    if not norm:
        raise DecomposeError("no subtasks given")

    executor = TicketExecutor(kind="llm", mode="automatic", handler=assignee) if assignee else None
    agent_labels = [f"agent:{assignee}"] if assignee else []
    created = [
        pf.create_ticket(name=sub["name"], **_child_data(
            parent, parent_id, sub, index, priority, sprint, executor, agent_labels, source))
        for index, sub in enumerate(norm, start=1)
    ]

    child_ids = [c.id for c in created]
    if sequential:  # stack: each subtask waits on the previous → strict order, single runnable front
        for prev, cur in zip(child_ids, child_ids[1:]):
            pf.update_ticket(cur, blocked_by=[prev])
    pf.update_ticket(parent_id, children=_dedup([*(parent.children or []), *child_ids]))
    if block_parent:
        pf.update_ticket(parent_id, blocked_by=_dedup([*(parent.blocked_by or []), *child_ids]))
    return created


def add_dependency(pf: Any, ticket_id: str, *, after: list[str] | None = None,
                   before: list[str] | None = None) -> dict:
    """Declare ordering between EXISTING tickets (git-like sequencing primitive).

    ``after`` = this ticket is ``blocked_by`` those (runs after them); ``before`` = those
    become ``blocked_by`` this one (they run after it). Idempotent, validates existence."""
    t = pf.get_ticket(ticket_id)
    if not t:
        raise DecomposeError(f"ticket {ticket_id} not found")
    after = [a for a in (after or []) if a]
    before = [b for b in (before or []) if b]
    for dep in [*after, *before]:
        if dep == ticket_id:
            raise DecomposeError("a ticket cannot depend on itself")
        if not pf.get_ticket(dep):
            raise DecomposeError(f"dependency ticket {dep} not found")
    if after:
        pf.update_ticket(ticket_id, blocked_by=_dedup([*(t.blocked_by or []), *after]))
    for b in before:
        bt = pf.get_ticket(b)
        pf.update_ticket(b, blocked_by=_dedup([*(bt.blocked_by or []), ticket_id]))
    return {"ticket": ticket_id, "after": after, "before": before}


def group_tickets(pf: Any, group_name: str, ticket_ids: list[str]) -> list[str]:
    """Gather related tickets under a named group (epic). Sets ``group`` + ``group:<name>``
    label on each existing ticket. Returns the IDs actually updated."""
    name = str(group_name or "").strip()
    if not name:
        raise DecomposeError("group name required")
    updated = []
    for tid in ticket_ids:
        t = pf.get_ticket(tid)
        if not t:
            continue
        labels = _dedup([*(t.labels or []), f"group:{name}"])
        pf.update_ticket(tid, group=name, labels=labels)
        updated.append(tid)
    return updated


def build_tree(pf: Any, root_id: str) -> dict:
    """Nested ``{id, name, status, children:[...]}`` decomposition tree (cycle-safe)."""
    root = pf.get_ticket(root_id)
    if not root:
        raise DecomposeError(f"ticket {root_id} not found")
    return _tree_node(pf, root, set())


def _status_str(t: Any) -> str:
    status = getattr(t, "status", "")
    return status.value if hasattr(status, "value") else str(status)


def _tree_node(pf: Any, t: Any, seen: set) -> dict:
    seen.add(t.id)
    children = []
    for cid in (t.children or []):
        if cid in seen:
            continue
        child = pf.get_ticket(cid)
        if child:
            children.append(_tree_node(pf, child, seen))
    return {"id": t.id, "name": t.name, "status": _status_str(t), "children": children}


def tree_progress(pf: Any, root_id: str) -> dict:
    """Roll-up completion of a decomposition: how many leaf/child subtasks are done."""
    tree = build_tree(pf, root_id)
    total = done = 0

    def _walk(node: dict) -> None:
        nonlocal total, done
        for c in node["children"]:
            total += 1
            if c["status"] in ("done", "canceled"):
                done += 1
            _walk(c)

    _walk(tree)
    return {"root": root_id, "subtasks": total, "done": done,
            "complete": total > 0 and done == total, "tree": tree}


def _absorb_outputs(target: Any, child: Any) -> tuple[Any, list[str], int]:
    """Fold child's notes + files onto the target. Returns (outputs, files, note_count)."""
    from planfile import TicketOutputs
    notes = list((target.outputs.notes if target.outputs else []) or [])
    notes.extend((child.outputs.notes if child.outputs else []) or [])
    notes.append(f"merged from {child.id}: {child.name}")
    out = target.outputs.model_dump() if target.outputs else {}
    out["notes"] = notes
    files = _dedup([*(target.files or []), *(child.files or [])])
    return TicketOutputs(**out), files, len(notes)


def _detach_from_parent(pf: Any, child: Any) -> None:
    """Drop a folded child from its parent's children/blocked_by so the epic isn't held by it."""
    if not child.parent:
        return
    parent = pf.get_ticket(child.parent)
    if parent:
        pf.update_ticket(
            child.parent,
            children=[c for c in (parent.children or []) if c != child.id],
            blocked_by=[b for b in (parent.blocked_by or []) if b != child.id],
        )


def merge_ticket(pf: Any, child_id: str, into_id: str) -> dict:
    """Refactor: fold ``child_id`` back into ``into_id`` (git squash-like).

    Moves the child's notes + files onto the target, cancels the child, and detaches it from
    its parent's ``children``/``blocked_by`` so the epic is no longer held by a folded task."""
    child = pf.get_ticket(child_id)
    target = pf.get_ticket(into_id)
    if not child:
        raise DecomposeError(f"child ticket {child_id} not found")
    if not target:
        raise DecomposeError(f"target ticket {into_id} not found")
    if child_id == into_id:
        raise DecomposeError("cannot merge a ticket into itself")

    outputs, files, note_count = _absorb_outputs(target, child)
    pf.update_ticket(into_id, outputs=outputs, files=files)
    pf.update_ticket(child_id, status="canceled")
    _detach_from_parent(pf, child)
    return {"merged": child_id, "into": into_id, "files": len(files), "notes": note_count}
