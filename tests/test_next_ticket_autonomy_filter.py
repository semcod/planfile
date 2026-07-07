"""next_ticket must not hand an autonomous queue a ticket that is frozen (autonomy-frontier),
waiting on a human, or off the active delivery goal — even though its blocked_by is empty.

Root cause this guards: koru selects work via `planfile ticket next`; without this filter it kept
re-serving the same un-doable human/frontier ticket (pick → fail → reopen → pick), which is why
the same ticket needed unblocking over and over.
"""
from __future__ import annotations

import pytest

from planfile import Planfile
from planfile.core.models import Ticket


def _mk(**kw) -> Ticket:
    kw.setdefault("name", "n")
    return Ticket(id=kw.pop("id", "T"), **kw)


def test_autonomy_blocked_recognises_frontier_and_human(monkeypatch):
    monkeypatch.delenv("PLANFILE_NO_AUTONOMY_FILTER", raising=False)
    assert Planfile._autonomy_blocked(_mk(labels=["autonomy-frontier"])) is True
    assert Planfile._autonomy_blocked(_mk(labels=["actor:human"])) is True
    assert Planfile._autonomy_blocked(_mk(labels=["waiting:node"])) is True
    assert Planfile._autonomy_blocked(_mk(labels=["needs-human:pypi-token"])) is True
    assert Planfile._autonomy_blocked(_mk(labels=["code", "bug"])) is False


def test_autonomy_filter_can_be_disabled(monkeypatch):
    monkeypatch.setenv("PLANFILE_NO_AUTONOMY_FILTER", "1")
    assert Planfile._autonomy_blocked(_mk(labels=["autonomy-frontier"])) is False


def test_goal_freeze_freezes_off_goal_only(monkeypatch):
    monkeypatch.setenv("CURRENT_GOAL", "signal.message.send")
    assert Planfile._goal_frozen(_mk(name="refactor dashboard", labels=["refactor"])) is True
    assert Planfile._goal_frozen(_mk(name="signal draft", labels=["goal:signal.message.send"])) is False
    assert Planfile._goal_frozen(_mk(name="send a signal message", labels=[])) is False  # domain in text


def test_no_goal_freezes_nothing(monkeypatch, tmp_path):
    monkeypatch.delenv("CURRENT_GOAL", raising=False)
    monkeypatch.setenv("URIRUN_CURRENT_GOAL", str(tmp_path / "absent.json"))  # no ifuri goal file
    assert Planfile._goal_frozen(_mk(name="refactor", labels=["refactor"])) is False


def test_next_ticket_skips_frontier_prefers_actionable(monkeypatch):
    monkeypatch.delenv("CURRENT_GOAL", raising=False)
    monkeypatch.setattr(Planfile, "_goal_frozen", staticmethod(lambda t: False))  # isolate autonomy filter
    frontier = _mk(id="F", name="link signal", labels=["actor:human"], priority="critical")
    code = _mk(id="C", name="fix parser", labels=["code"], priority="normal")
    pf = Planfile.__new__(Planfile)
    monkeypatch.setattr(pf, "list_tickets", lambda **k: [frontier, code])
    monkeypatch.setattr(pf, "get_ticket", lambda i: None)
    nxt = pf.next_ticket()
    assert nxt is not None and nxt.id == "C"  # critical frontier F skipped; actionable C served


# ── named runnability contract + debug report ─────────────────────────────────

def test_runnability_skip_reason_names_each_axis(monkeypatch):
    monkeypatch.delenv("CURRENT_GOAL", raising=False)
    pf = Planfile.__new__(Planfile)
    monkeypatch.setattr(pf, "get_ticket", lambda i: None)
    assert pf.runnability_skip_reason(_mk(labels=["autonomy-frontier"])) == "autonomy-frontier"
    assert pf.runnability_skip_reason(_mk(labels=["actor:human"])) == "actor:human"
    assert pf.runnability_skip_reason(_mk(labels=["waiting:node"])) == "waiting:node"
    assert pf.runnability_skip_reason(_mk(labels=["code"])) == ""  # runnable


def test_runnability_separates_dependency_from_resource_wait(monkeypatch):
    # blocked_by (ticket→ticket dependency) is a DISTINCT axis from waiting:* (resource wait)
    pf = Planfile.__new__(Planfile)
    monkeypatch.setattr(pf, "get_ticket", lambda i: None)  # dep missing → unsatisfied
    assert pf.runnability_skip_reason(_mk(blocked_by=["DEP-1"])) == "blocked_by:DEP-1"


def test_runnable_report_splits_servable_and_skipped(monkeypatch):
    monkeypatch.delenv("CURRENT_GOAL", raising=False)
    tickets = [
        _mk(id="C1", name="fix", labels=["code"], priority="normal"),
        _mk(id="H1", name="link", labels=["actor:human"], priority="critical"),
        _mk(id="W1", name="deploy", labels=["waiting:node"]),
    ]
    pf = Planfile.__new__(Planfile)
    monkeypatch.setattr(pf, "list_tickets", lambda **k: tickets)
    monkeypatch.setattr(pf, "get_ticket", lambda i: None)
    rep = pf.runnable_report()
    assert rep["selected"] == "C1" and rep["servable"] == ["C1"]
    reasons = {r["id"]: r["reason"] for r in rep["skipped"]}
    assert reasons == {"H1": "actor:human", "W1": "waiting:node"}
