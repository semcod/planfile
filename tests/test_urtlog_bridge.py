"""Tests for optional, fail-open uritime-urtlog bridge in Planfile."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from planfile.urtlog_bridge import (
    load_planfile_queue_brief,
    maybe_emit_ticket_created,
    maybe_emit_ticket_dependency,
    maybe_emit_ticket_event,
    resolve_state_dir,
)


def test_bridge_inactive_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("URTLOG_STATE_DIR", raising=False)
    assert resolve_state_dir() is None
    t = SimpleNamespace(id="PLF-001", name="Bootstrap", sprint="backlog", priority="high", status="open")
    assert maybe_emit_ticket_created(t) == {"emitted": False, "reason": "disabled"}
    assert maybe_emit_ticket_dependency("PLF-003", after=["PLF-001"]) == {"emitted": False, "reason": "disabled"}
    assert maybe_emit_ticket_event("block", t, reason="waiting") == {"emitted": False, "reason": "disabled"}
    brief = load_planfile_queue_brief()
    assert brief["enabled"] is False


def test_bridge_fail_open_when_urtlog_missing(tmp_path: Path) -> None:
    t = SimpleNamespace(id="PLF-001", name="Bootstrap", sprint="backlog", priority="high", status="open")
    with mock.patch("planfile.urtlog_bridge.importlib.import_module", side_effect=ImportError("no urtlog")):
        assert maybe_emit_ticket_created(t, state_dir=tmp_path) == {
            "emitted": False,
            "reason": "urtlog_not_installed",
        }
        assert maybe_emit_ticket_dependency("PLF-003", after=["PLF-001"], state_dir=tmp_path) == {
            "emitted": False,
            "reason": "urtlog_not_installed",
        }


def test_live_planfile_dag_blockers_and_queue_brief(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if importlib.util.find_spec("urtlog") is None:
        return

    state_dir = tmp_path / "urtlog-state"
    monkeypatch.setenv("URTLOG_STATE_DIR", str(state_dir))

    t1 = SimpleNamespace(id="PLF-001", name="Bootstrap Jetson IMG", sprint="backlog", priority="high", status="open", labels=["coding"], blocked_by=[])
    t2 = SimpleNamespace(id="PLF-002", name="Flash microSD & boot Jetson", sprint="backlog", priority="high", status="open", labels=["operator"], blocked_by=[])
    t3 = SimpleNamespace(id="PLF-003", name="Przygotuj recepture pierwszego startu Jetsona z SSH na klucz", sprint="backlog", priority="high", status="open", labels=["coding"], blocked_by=[])
    t4 = SimpleNamespace(id="PLF-004", name="Dodaj kontrolowany handoff SSH Jetsona do Heyasa", sprint="backlog", priority="normal", status="open", labels=["coding"], blocked_by=[])
    t5 = SimpleNamespace(id="PLF-005", name="Zbuduj spersonalizowany IMG i sprawdz SSH", sprint="backlog", priority="normal", status="open", labels=["operator"], blocked_by=[])

    for t in (t1, t2, t3, t4, t5):
        res = maybe_emit_ticket_created(t, created=True)
        assert res["emitted"] is True

    assert maybe_emit_ticket_dependency("PLF-003", after=["PLF-001"])["emitted"] is True
    assert maybe_emit_ticket_dependency("PLF-004", after=["PLF-003"])["emitted"] is True
    assert maybe_emit_ticket_dependency("PLF-005", after=["PLF-002", "PLF-004"])["emitted"] is True

    t1_updated = SimpleNamespace(**{**t1.__dict__, "status": "blocked"})
    t2_blocked = SimpleNamespace(**{**t2.__dict__, "status": "blocked"})
    assert maybe_emit_ticket_event("update", t1, note="Fabryczny IMG JetPack 6.2.1 zweryfikowany.")["emitted"] is True
    assert maybe_emit_ticket_event("block", t1_updated, reason="Oczekiwanie na profil OneDev PLF-27200 i VA-084.")["emitted"] is True
    assert maybe_emit_ticket_event("block", t2_blocked, reason="Operator musi wskazac microSD i uruchomic Jetson.")["emitted"] is True

    brief = load_planfile_queue_brief(state_dir=state_dir)
    assert brief["enabled"] is True
    assert brief["ticket_count"] == 5
    assert brief["event_count"] == 11
    assert set(brief["blocked"]) == {"PLF-001", "PLF-002"}
    assert {"PLF-003", "PLF-004", "PLF-005"}.issubset(set(brief["queued"]))

    by_id = {item["ticket_id"]: item for item in brief["tickets"]}
    assert by_id["PLF-005"]["depends_on"] == ["PLF-002", "PLF-004"]
    assert "PLF-27200" in (by_id["PLF-001"]["reason"] or "")

    urtlog_mod = importlib.import_module("urtlog")
    ctx = urtlog_mod.AccessContext(
        "heyasa",
        roles=frozenset({"assistant"}),
        groups=frozenset({"ops"}),
        max_sensitivity="internal",
    )
    with urtlog_mod.UrtClient(state_dir, source="planfile", repository="semcod/planfile") as client:
        dep_events = client.store.query(ctx, source="planfile", op_prefix="op/planfile/ticket/depend/")
        block_events = client.store.query(ctx, source="planfile", op_prefix="op/planfile/ticket/block/")
        assert len(dep_events) == 3
        assert len(block_events) == 2
