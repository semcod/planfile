"""Tests for parallel ticket scheduling, dynamic file scoping, and exclusion."""
import pytest
from planfile import Planfile


@pytest.fixture
def pf(tmp_path):
    return Planfile(str(tmp_path))


def test_next_tickets_comma_separated_files(pf):
    # Ticket A touches foo.py and bar.py as a comma-separated string
    t_a = pf.create_ticket(
        name="Task A",
        files=["src/foo.py,src/bar.py"],
        priority="high",
    )
    # Ticket B touches bar.py as a single file
    t_b = pf.create_ticket(
        name="Task B",
        files=["src/bar.py"],
        priority="high",
    )
    # Ticket C touches baz.py
    t_c = pf.create_ticket(
        name="Task C",
        files=["src/baz.py"],
        priority="high",
    )

    # With disjoint_files=True, Task A and Task B overlap on src/bar.py!
    # So requesting count=2 should select Task A and Task C, NOT Task A and Task B.
    selected = pf.next_tickets(count=2, disjoint_files=True)
    ids = [t.id for t in selected]
    assert t_a.id in ids
    assert t_b.id not in ids
    assert t_c.id in ids


def test_next_tickets_locked_files(pf):
    t_a = pf.create_ticket(
        name="Task A",
        files=["src/module_a.py"],
        priority="high",
    )
    t_b = pf.create_ticket(
        name="Task B",
        files=["src/module_b.py"],
        priority="high",
    )

    # If src/module_a.py is currently locked by a concurrently executing worker:
    selected = pf.next_tickets(
        count=1,
        disjoint_files=True,
        locked_files={"src/module_a.py"},
    )
    assert len(selected) == 1
    assert selected[0].id == t_b.id


def test_next_tickets_exclude_ids(pf):
    t_a = pf.create_ticket(
        name="Task A",
        priority="high",
    )
    t_b = pf.create_ticket(
        name="Task B",
        priority="normal",
    )

    # Exclude Task A (e.g. already in flight)
    selected = pf.next_tickets(count=1, exclude_ids={t_a.id})
    assert len(selected) == 1
    assert selected[0].id == t_b.id


def test_execution_waves_status_filtering(pf):
    t_a = pf.create_ticket(name="Task A")
    t_b = pf.create_ticket(name="Task B", blocked_by=[t_a.id])

    waves_before = pf.execution_waves(status="open")
    assert len(waves_before) == 2
    assert t_a.id in waves_before[0]
    assert t_b.id in waves_before[1]

    # Complete Task A
    pf.complete_ticket(t_a.id)

    # Only Task B is open now; Task A is satisfied so Task B has no open blockers in id_set
    waves_after = pf.execution_waves(status="open")
    assert len(waves_after) == 1
    assert t_b.id in waves_after[0]
