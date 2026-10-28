"""Semantic layer: duplicate detection, decomposition suggestion, objective coverage.

Runs offline with deterministic producer-present/absent fixtures. Embedding and
completion inputs are exercised with local stubs, without external models."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from planfile import Planfile
from planfile.core import semantic as sem
from planfile.core import ticket_radar as radar

ADVISORY = (
    "\n\n**Ticket impact radar (advisory)**\n\n"
    "- Complexity: `M`\n"
    "- Score: `36/100`\n"
    "- Estimated effort: `37 min`\n"
    "- Split recommended: `yes`\n\n"
    "This estimate does not grant execution, review or merge authority."
)


@pytest.fixture(autouse=True, params=[False, True], ids=["producer-absent", "producer-present"])
def advisory_producer(request, monkeypatch):
    """Exercise real enrichment with a valid, deterministic transport response."""
    def bundle(payload, root, deadline):
        if not request.param:
            raise FileNotFoundError("optional producer absent")
        ticket = json.loads(payload)
        assessment = {
            "schema": "subactor.ticket-radar/v1", "ticket_ref": ticket["id"],
            "complexity": "M", "score": 36, "estimate": {"minutes": 37},
            "split": {"recommended": True},
        }
        return json.dumps({
            "schema": "subactor.ticket-radar-bundle/v1", "jsonl": json.dumps(assessment),
        }).encode()

    monkeypatch.setattr(radar, "_bundle", bundle)
    monkeypatch.setattr(sem, "_embed_model", lambda: None)
    monkeypatch.setattr(sem, "_llm_model", lambda: None)
    return ADVISORY if request.param else ""


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


def test_suggest_decomposition_from_bullets(tmp_path, advisory_producer):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="Refactor", description="- extract parser\n- extract writer\n- add tests")
    assert t.description == "- extract parser\n- extract writer\n- add tests" + advisory_producer
    out = sem.suggest_decomposition(pf, t.id, use_llm=False)
    assert len(out["subtasks"]) == 3
    assert out["subtasks"][0]["name"] == "extract parser"


def test_suggest_decomposition_atomic_ticket(tmp_path, advisory_producer):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="Rename variable x to count")
    assert t.description == advisory_producer
    out = sem.suggest_decomposition(pf, t.id, use_llm=False)
    assert out["atomic"] is True and out["subtasks"] == []


# ── 3. objective coverage ─────────────────────────────────────────────────────

def test_coverage_flags_uncovered_objective(tmp_path, advisory_producer):
    pf = _pf(tmp_path)
    login = pf.create_ticket(name="Implement OAuth login", description="OAuth login with Google")
    reset = pf.create_ticket(name="Add password reset", description="password reset via email")
    assert login.description == "OAuth login with Google" + advisory_producer
    assert reset.description == "password reset via email" + advisory_producer
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


def test_semantic_results_match_human_only_tickets(tmp_path, advisory_producer):
    pf = _pf(tmp_path)
    data = [
        {"name": "Fix login timeout", "description": "Users get logged out after 5 minutes"},
        {"name": "Fix login timeout bug", "description": "Users are logged out after 5 minutes"},
        {"name": "Refactor", "description": "- extract parser\n- extract writer\n- add tests"},
        {"name": "Rename variable x to count", "description": ""},
        {"name": "Connectives", "description": "extract parser; extract writer"},
    ]
    enriched = [pf.create_ticket(**item) for item in data]
    bare = [ticket.model_copy(update={"description": item["description"]})
            for ticket, item in zip(enriched, data, strict=True)]
    human_pf = SimpleNamespace(list_tickets=lambda **kwargs: bare)
    for ticket, human, item in zip(enriched, bare, data, strict=True):
        assert ticket.description == item["description"] + advisory_producer
        assert sem.ticket_text(ticket) == sem.ticket_text(human)
        assert sem.heuristic_subtasks(ticket) == sem.heuristic_subtasks(human)
    assert sem.detect_duplicates(pf, threshold=0.4) == sem.detect_duplicates(human_pf, threshold=0.4)
    objectives = ["authentication and login", "billing and invoicing"]
    assert sem.coverage_report(pf, objectives=objectives, threshold=0.08) == sem.coverage_report(
        human_pf, objectives=objectives, threshold=0.08,
    )


@pytest.mark.parametrize("description", ["", "- login\n- logout\n  Zażółć 🐍  "])
def test_embedding_and_completion_receive_human_content(tmp_path, monkeypatch, advisory_producer, description):
    pf = _pf(tmp_path)
    name = "Ship auth"
    criteria = ["Keep user criterion"]
    ticket = pf.create_ticket(name=name, description=description, acceptance_criteria=criteria)
    assert ticket.description == description + advisory_producer
    human_text = "\n".join(part for part in [name, description, criteria[0]] if part)
    observed_embeddings, observed_prompts = [], []

    def embedding(*, model, input):
        assert model == "fixture-embedding"
        observed_embeddings.append(input)
        return {"data": [{"embedding": [1.0, 0.0]} for _ in input]}

    subtasks = [{"name": "Login", "description": "Human subtask", "files": ["auth.py"]}]

    def completion(**kwargs):
        assert kwargs["model"] == "fixture-completion"
        observed_prompts.append(kwargs["messages"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps({"subtasks": subtasks}),
        ))])

    monkeypatch.setattr(sem, "_embed_model", lambda: "fixture-embedding")
    monkeypatch.setattr(sem, "_llm_model", lambda: "fixture-completion")
    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(embedding=embedding, completion=completion))
    assert sem.detect_duplicates(pf)["method"] == "embed"
    report = sem.coverage_report(pf, objectives=["login"])
    assert report["method"] == "embed" and report["complete"] is True
    assert observed_embeddings == [[human_text], ["login", human_text]]
    result = sem.suggest_decomposition(pf, ticket.id)
    assert result == {"ticket": ticket.id, "method": "llm", "subtasks": subtasks, "atomic": False}
    assert observed_prompts == [[{"role": "user", "content": (
        "Break this engineering ticket into at most 6 smaller, independently-executable subtasks. "
        "Each subtask should touch a DISJOINT set of files so they never conflict, and be ordered if dependent. "
        'Return ONLY JSON: {"subtasks":[{"name":str,"description":str,"files":[str],"sequential":bool}]}.\n\n'
        f"TICKET: {name}\n\n{description}"
    )}]]


def test_human_heading_names_and_criteria_retain_semantics():
    description = radar.ADVISORY_HEADING + "\n\n- Human task\n- Other task"
    ticket = SimpleNamespace(name=ADVISORY, description=description, acceptance_criteria=[ADVISORY])
    assert sem.ticket_text(ticket) == ADVISORY + "\n" + description + "\n" + ADVISORY
    assert sem.heuristic_subtasks(ticket) == [
        {"name": "Human task", "description": "Human task"},
        {"name": "Other task", "description": "Other task"},
    ]
