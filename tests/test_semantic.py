"""Semantic layer: duplicate detection, decomposition suggestion, objective coverage.

Runs offline on the deterministic lexical fallback (no embedding model / LLM in CI). The
embed/LLM paths are exercised only when a model env var is set, so tests are stable."""
from __future__ import annotations

import pytest

from planfile import Planfile
from planfile.core import semantic as sem


def _pf(tmp_path):
    return Planfile(str(tmp_path))


# ── lexical similarity ────────────────────────────────────────────────────────

def test_lexical_similarity_high_for_paraphrase():
    a = "Add retry with exponential backoff to the HTTP client"
    b = "Implement exponential backoff retry in the HTTP client"
    assert sem.lexical_similarity(a, b) > 0.4


def test_lexical_similarity_low_for_unrelated():
    a = "Add retry with exponential backoff to the HTTP client"
    b = "Update the marketing landing page copy for launch"
    assert sem.lexical_similarity(a, b) < 0.15


def test_lexical_similarity_symmetric_and_bounded():
    a, b = "refactor the parser module", "refactor parser module now"
    s = sem.lexical_similarity(a, b)
    assert 0.0 <= s <= 1.0
    assert sem.lexical_similarity(a, b) == sem.lexical_similarity(b, a)


# ── 1. duplicate detection ────────────────────────────────────────────────────

def test_detect_duplicates_finds_near_identical(tmp_path):
    pf = _pf(tmp_path)
    pf.create_ticket(name="Fix login timeout", description="Users get logged out after 5 minutes")
    pf.create_ticket(name="Fix login timeout bug", description="Users are logged out after 5 minutes")
    pf.create_ticket(name="Add dark mode", description="Provide a dark theme toggle")
    rep = sem.detect_duplicates(pf, threshold=0.4)
    assert rep["method"] == "lexical"
    ids = {frozenset((d["a"], d["b"])) for d in rep["duplicates"]}
    # the two login tickets pair up; dark mode is not flagged
    assert any("Add dark mode" not in (d["a_name"] + d["b_name"]) for d in rep["duplicates"])
    assert len(rep["duplicates"]) >= 1


def test_detect_duplicates_excludes_parent_child(tmp_path):
    pf = _pf(tmp_path)
    from planfile.core.decompose import split_ticket
    parent = pf.create_ticket(name="Build export feature export csv")
    split_ticket(pf, parent.id, ["Build export feature export csv rows"])
    rep = sem.detect_duplicates(pf, threshold=0.3)
    # a subtask is never a duplicate of its own epic
    for d in rep["duplicates"]:
        assert not {d["a"], d["b"]} == {parent.id, pf.get_ticket(parent.id).children[0]}


# ── 2. decomposition suggestion ───────────────────────────────────────────────

def test_suggest_decomposition_from_acceptance_criteria(tmp_path):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="Ship auth",
                         acceptance_criteria=["login works", "logout works", "session persists"])
    out = sem.suggest_decomposition(pf, t.id, use_llm=False)
    assert out["method"] == "heuristic"
    assert [s["name"] for s in out["subtasks"]] == ["login works", "logout works", "session persists"]
    assert out["atomic"] is False


def test_suggest_decomposition_from_bullets(tmp_path):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="Refactor", description="- extract parser\n- extract writer\n- add tests")
    out = sem.suggest_decomposition(pf, t.id, use_llm=False)
    assert len(out["subtasks"]) == 3
    assert out["subtasks"][0]["name"] == "extract parser"


def test_suggest_decomposition_atomic_ticket(tmp_path):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="Rename variable x to count")
    out = sem.suggest_decomposition(pf, t.id, use_llm=False)
    assert out["atomic"] is True and out["subtasks"] == []


# ── 3. objective coverage ─────────────────────────────────────────────────────

def test_coverage_flags_uncovered_objective(tmp_path):
    pf = _pf(tmp_path)
    pf.create_ticket(name="Implement OAuth login", description="OAuth login with Google")
    pf.create_ticket(name="Add password reset", description="password reset via email")
    objectives = ["authentication and login", "billing and invoicing"]
    rep = sem.coverage_report(pf, objectives=objectives, threshold=0.08)
    covered_objs = {c["objective"] for c in rep["covered"]}
    assert "authentication and login" in covered_objs
    assert "billing and invoicing" in rep["uncovered"]  # nothing covers billing
    assert rep["complete"] is False
    assert 0.0 <= rep["coverage"] <= 1.0


def test_coverage_no_objectives_is_trivially_complete(tmp_path):
    pf = _pf(tmp_path)
    pf.create_ticket(name="x")
    rep = sem.coverage_report(pf, objectives=[])
    assert rep["objectives"] == 0 and rep["coverage"] == 1.0
