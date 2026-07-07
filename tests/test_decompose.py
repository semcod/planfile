"""Git-like ticket decomposition: split / group / tree / merge."""
from __future__ import annotations

import pytest

from planfile import Planfile
from planfile.core.decompose import (
    DecomposeError,
    add_dependency,
    build_tree,
    group_tickets,
    merge_ticket,
    prune_dangling_dependencies,
    split_ticket,
    tree_progress,
)


def _pf(tmp_path):
    return Planfile(str(tmp_path))


def test_split_creates_children_and_blocks_parent(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="Build feature X", priority="high", labels=["area:api"])
    children = split_ticket(pf, parent.id, ["design", "implement", "test"], assignee="claude")

    assert len(children) == 3
    # each child links back to the parent and inherits priority + labels + parent tag + agent
    for c in children:
        assert c.parent == parent.id
        assert c.priority == "high"
        assert "area:api" in c.labels
        assert f"parent:{parent.id}" in c.labels
        assert "agent:claude" in c.labels
        assert c.executor and c.executor.handler == "claude"

    reloaded = pf.get_ticket(parent.id)
    assert reloaded.children == [c.id for c in children]
    # epic is blocked_by all subtasks → completes last
    assert set(reloaded.blocked_by) == {c.id for c in children}


def test_split_file_scoping_keeps_subtasks_disjoint(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="Refactor module")
    children = split_ticket(pf, parent.id, [
        {"name": "split core", "files": ["core.py"]},
        {"name": "split cli", "files": ["cli.py"]},
    ])
    assert children[0].files == ["core.py"]
    assert children[1].files == ["cli.py"]
    # disjoint file sets → no two subtasks touch the same file (conflict-free)
    assert set(children[0].files).isdisjoint(children[1].files)


def test_split_no_block_leaves_parent_runnable(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="Epic")
    split_ticket(pf, parent.id, ["a", "b"], block_parent=False)
    reloaded = pf.get_ticket(parent.id)
    assert reloaded.children  # still tracked
    assert reloaded.blocked_by == []  # but not held


def test_split_unknown_parent_raises(tmp_path):
    pf = _pf(tmp_path)
    with pytest.raises(DecomposeError):
        split_ticket(pf, "NOPE-1", ["a"])


def test_split_requires_subtasks(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="Empty")
    with pytest.raises(DecomposeError):
        split_ticket(pf, parent.id, [])


def test_sequential_split_stacks_subtasks_in_order(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="Pipeline")
    kids = split_ticket(pf, parent.id, ["a", "b", "c"], sequential=True)
    a, b, c = kids
    # git-stacked: b waits on a, c waits on b; a is the single runnable front
    assert pf.get_ticket(a.id).blocked_by == []
    assert pf.get_ticket(b.id).blocked_by == [a.id]
    assert pf.get_ticket(c.id).blocked_by == [b.id]


def test_parallel_split_has_no_inter_child_deps(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="Fanout")
    kids = split_ticket(pf, parent.id, ["a", "b"])  # sequential=False default
    for k in kids:
        assert pf.get_ticket(k.id).blocked_by == []  # siblings independent


def test_add_dependency_after_and_before(tmp_path):
    pf = _pf(tmp_path)
    a = pf.create_ticket(name="a")
    b = pf.create_ticket(name="b")
    c = pf.create_ticket(name="c")
    # b runs after a; c runs after b
    add_dependency(pf, b.id, after=[a.id])
    add_dependency(pf, b.id, before=[c.id])
    assert pf.get_ticket(b.id).blocked_by == [a.id]
    assert pf.get_ticket(c.id).blocked_by == [b.id]


def test_add_dependency_rejects_self_and_missing(tmp_path):
    pf = _pf(tmp_path)
    a = pf.create_ticket(name="a")
    with pytest.raises(DecomposeError):
        add_dependency(pf, a.id, after=[a.id])
    with pytest.raises(DecomposeError):
        add_dependency(pf, a.id, after=["GHOST-9"])


def test_prune_dangling_dependencies_unblocks(tmp_path):
    pf = _pf(tmp_path)
    real = pf.create_ticket(name="real blocker")
    t = pf.create_ticket(name="held")
    # one real blocker + two ghosts that never existed
    add_dependency(pf, t.id, after=[real.id])
    pf.update_ticket(t.id, blocked_by=[real.id, "GHOST-1", "GHOST-2"])
    rep = prune_dangling_dependencies(pf)
    assert t.id in [c["ticket"] for c in rep["cleaned"]]
    reloaded = pf.get_ticket(t.id)
    assert reloaded.blocked_by == [real.id]  # ghosts gone, real kept
    assert t.id not in rep["unblocked"]  # still has a real blocker


def test_prune_fully_unblocks_when_all_ghosts(tmp_path):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="held by ghosts only")
    pf.update_ticket(t.id, blocked_by=["GONE-7", "GONE-8"])
    rep = prune_dangling_dependencies(pf)
    assert t.id in rep["unblocked"]
    assert pf.get_ticket(t.id).blocked_by == []


def test_group_tags_related_tickets(tmp_path):
    pf = _pf(tmp_path)
    a = pf.create_ticket(name="a")
    b = pf.create_ticket(name="b")
    updated = group_tickets(pf, "onboarding", [a.id, b.id, "MISSING-9"])
    assert updated == [a.id, b.id]  # missing skipped
    for tid in (a.id, b.id):
        t = pf.get_ticket(tid)
        assert t.group == "onboarding"
        assert "group:onboarding" in t.labels


def test_tree_and_progress_rollup(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="root")
    kids = split_ticket(pf, parent.id, ["a", "b"])
    tree = build_tree(pf, parent.id)
    assert tree["id"] == parent.id
    assert {c["id"] for c in tree["children"]} == {k.id for k in kids}

    prog = tree_progress(pf, parent.id)
    assert prog["subtasks"] == 2 and prog["done"] == 0 and prog["complete"] is False
    pf.update_ticket(kids[0].id, status="done")
    pf.update_ticket(kids[1].id, status="done")
    prog2 = tree_progress(pf, parent.id)
    assert prog2["done"] == 2 and prog2["complete"] is True


def test_merge_folds_child_back_and_detaches(tmp_path):
    pf = _pf(tmp_path)
    parent = pf.create_ticket(name="epic")
    kids = split_ticket(pf, parent.id, [
        {"name": "keep", "files": ["a.py"]},
        {"name": "fold", "files": ["b.py"]},
    ])
    keep, fold = kids
    result = merge_ticket(pf, fold.id, keep.id)

    assert result["merged"] == fold.id and result["into"] == keep.id
    folded = pf.get_ticket(fold.id)
    assert str(folded.status) in ("TicketStatus.canceled", "canceled")
    # target absorbed the folded ticket's file
    target = pf.get_ticket(keep.id)
    assert set(target.files) >= {"a.py", "b.py"}
    # parent no longer blocked/tracked by the folded child
    reloaded = pf.get_ticket(parent.id)
    assert fold.id not in reloaded.children
    assert fold.id not in reloaded.blocked_by


def test_merge_into_self_raises(tmp_path):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="x")
    with pytest.raises(DecomposeError):
        merge_ticket(pf, t.id, t.id)
