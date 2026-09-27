"""Tests for priority weighting and medium priority normalization (ticket-159)."""

from datetime import datetime, timezone

from planfile import Planfile
from planfile.core.models.ticket import Ticket


def test_ticket_model_priority_normalization():
    """Verify priority aliases like 'medium' and 'med' normalize to 'normal'."""
    t1 = Ticket(id="PLF-1", name="Task 1", priority="medium")
    assert t1.priority == "normal"

    t2 = Ticket(id="PLF-2", name="Task 2", priority="MEDIUM")
    assert t2.priority == "normal"

    t3 = Ticket(id="PLF-3", name="Task 3", priority="med")
    assert t3.priority == "normal"

    t4 = Ticket(id="PLF-4", name="Task 4", priority="high")
    assert t4.priority == "high"

    t5 = Ticket(id="PLF-5", name="Task 5", priority="low")
    assert t5.priority == "low"

    t6 = Ticket(id="PLF-6", name="Task 6", priority="critical")
    assert t6.priority == "critical"


def test_ticket_sort_key_medium_ordering():
    """Verify _ticket_sort_key ranks medium/normal strictly ahead of low."""
    now = datetime.now(timezone.utc)
    t_crit = Ticket(id="PLF-1", name="Crit", priority="critical", created_at=now)
    t_high = Ticket(id="PLF-2", name="High", priority="high", created_at=now)
    t_norm = Ticket(id="PLF-3", name="Normal", priority="normal", created_at=now)
    # Directly instantiate with priority="medium" if bypassing model validator
    t_med = Ticket.model_construct(id="PLF-4", name="Medium", priority="medium", created_at=now, labels=[])
    t_low = Ticket(id="PLF-5", name="Low", priority="low", created_at=now)
    t_unk = Ticket.model_construct(id="PLF-6", name="Unknown", priority="unknown", created_at=now, labels=[])

    key_crit = Planfile._ticket_sort_key(t_crit)
    key_high = Planfile._ticket_sort_key(t_high)
    key_norm = Planfile._ticket_sort_key(t_norm)
    key_med = Planfile._ticket_sort_key(t_med)
    key_low = Planfile._ticket_sort_key(t_low)
    key_unk = Planfile._ticket_sort_key(t_unk)

    # Priority weight should be the first element in sort key tuple
    assert key_crit[0] == 0
    assert key_high[0] == 1
    assert key_norm[0] == 2
    assert key_med[0] == 2  # medium must NOT be 99!
    assert key_low[0] == 3
    assert key_unk[0] == 99

    tickets = [t_unk, t_low, t_med, t_norm, t_high, t_crit]
    sorted_tickets = sorted(tickets, key=Planfile._ticket_sort_key)
    sorted_ids = [t.id for t in sorted_tickets]

    # Critical first, then high, then normal/medium, then low, then unknown
    assert sorted_ids[0] == "PLF-1"
    assert sorted_ids[1] == "PLF-2"
    assert set(sorted_ids[2:4]) == {"PLF-3", "PLF-4"}
    assert sorted_ids[4] == "PLF-5"
    assert sorted_ids[5] == "PLF-6"
