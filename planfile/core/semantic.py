"""Semantic layer for planfile: duplicate detection, LLM-assisted decomposition, and
objective coverage of sprints/milestones.

Design: **embedding/LLM-first with a deterministic lexical fallback**. When an embedding
model (``PLANFILE_EMBED_MODEL`` / ``EMBED_MODEL``) or an LLM (``PLANFILE_LLM_MODEL`` /
``LLM_MODEL``) is configured AND litellm is importable, the high-fidelity path is used
(cosine similarity of embeddings; an LLM that proposes ordered, file-scoped subtasks and
maps objectives→tickets). Otherwise everything degrades cleanly to an offline token/trigram
method — so it always runs (CI gate) and never hard-fails on a missing model.

The functions here only *analyse* and *suggest*; applying a decomposition goes through
``planfile.core.decompose.split_ticket`` so the mutation stays in one place.
"""
from __future__ import annotations

import math
import os
import re
from typing import Any

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
# Small PL+EN stopword set so shared filler doesn't inflate similarity.
_STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "are", "be",
    "this", "that", "it", "as", "by", "at", "from", "into",
    "i", "oraz", "lub", "do", "na", "w", "we", "z", "ze", "o", "po", "przez", "dla", "aby",
    "jest", "sa", "to", "ten", "ta", "te", "jako", "gdy", "sie",
}


# ── text normalization ────────────────────────────────────────────────────────

def _tokens(text: str) -> set[str]:
    return {w for w in (m.group(0).lower() for m in _WORD_RE.finditer(text or "")) if w not in _STOP and len(w) > 2}


def _trigrams(text: str) -> set[str]:
    s = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def ticket_text(t: Any) -> str:
    """The text a ticket is compared on: name + description + acceptance criteria."""
    parts = [getattr(t, "name", "") or "", getattr(t, "description", "") or ""]
    parts.extend(getattr(t, "acceptance_criteria", None) or [])
    return "\n".join(p for p in parts if p)


# ── lexical similarity (offline, deterministic) ──────────────────────────────

def lexical_similarity(a: str, b: str) -> float:
    """Blend of content-token Jaccard (meaning) and trigram Jaccard (surface form)."""
    tok = _jaccard(_tokens(a), _tokens(b))
    tri = _jaccard(_trigrams(a), _trigrams(b))
    return round(0.7 * tok + 0.3 * tri, 4)


# ── embedding backend (optional, high fidelity) ──────────────────────────────

def _embed_model() -> str | None:
    return os.environ.get("PLANFILE_EMBED_MODEL") or os.environ.get("EMBED_MODEL")


def _llm_model() -> str | None:
    return os.environ.get("PLANFILE_LLM_MODEL") or os.environ.get("LLM_MODEL")


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]] | None:
    """Batch-embed texts via litellm; return None if no model/backend (→ lexical fallback)."""
    model = model or _embed_model()
    if not model or not texts:
        return None
    try:
        import litellm
        resp = litellm.embedding(model=model, input=list(texts))
        data = resp["data"] if isinstance(resp, dict) else resp.data
        return [row["embedding"] if isinstance(row, dict) else row.embedding for row in data]
    except Exception:  # noqa: BLE001 - any failure degrades to lexical
        return None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def similarity_matrix(texts: list[str]) -> tuple[list[list[float]], str]:
    """Pairwise similarity of texts. Returns (matrix, method) — 'embed' when embeddings are
    available, else deterministic 'lexical'."""
    vectors = embed_texts(texts)
    n = len(texts)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            score = cosine(vectors[i], vectors[j]) if vectors else lexical_similarity(texts[i], texts[j])
            matrix[i][j] = matrix[j][i] = round(score, 4)
    return matrix, ("embed" if vectors else "lexical")


# ── 1. duplicate detection ───────────────────────────────────────────────────

def detect_duplicates(pf: Any, *, threshold: float = 0.85, sprint: str = "current",
                      status: str | None = None) -> dict:
    """Find semantically-duplicate tickets. Returns pairs above ``threshold`` with score +
    method. embed-cosine when a model is set, else lexical. Excludes already-linked
    parent/child pairs (a subtask is not a duplicate of its epic)."""
    tickets = [t for t in pf.list_tickets(sprint=sprint) if not status or _status(t) == status]
    texts = [ticket_text(t) for t in tickets]
    matrix, method = similarity_matrix(texts)
    pairs = []
    for i in range(len(tickets)):
        for j in range(i + 1, len(tickets)):
            if matrix[i][j] >= threshold and not _related(tickets[i], tickets[j]):
                pairs.append({"a": tickets[i].id, "b": tickets[j].id,
                              "score": matrix[i][j], "a_name": tickets[i].name, "b_name": tickets[j].name})
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return {"method": method, "threshold": threshold, "duplicates": pairs, "checked": len(tickets)}


def _related(a: Any, b: Any) -> bool:
    return b.id in (a.children or []) or a.id in (b.children or []) or a.parent == b.id or b.parent == a.id


def _status(t: Any) -> str:
    s = getattr(t, "status", "")
    return s.value if hasattr(s, "value") else str(s)


# ── 2. decomposition suggestion (LLM + heuristic fallback) ───────────────────

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*\S)")
_CONNECTIVE_RE = re.compile(r"\s*(?:;|\band then\b|\bthen\b|\bnastępnie\b|\boraz\b)\s+", re.IGNORECASE)


def _bullet_lines(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        m = _BULLET_RE.match(line)
        if m:
            out.append(m.group(1).strip())
    return out


def heuristic_subtasks(ticket: Any) -> list[dict]:
    """Offline decomposition: acceptance criteria → subtasks; else bullet lines; else split on
    connectives. Returns [] when the ticket is already atomic (nothing to split)."""
    crit = getattr(ticket, "acceptance_criteria", None) or []
    if len(crit) >= 2:
        return [{"name": c[:80], "description": c} for c in crit]
    bullets = _bullet_lines(getattr(ticket, "description", "") or "")
    if len(bullets) >= 2:
        return [{"name": b[:80], "description": b} for b in bullets]
    body = (getattr(ticket, "description", "") or getattr(ticket, "name", "") or "").strip()
    parts = [p.strip() for p in _CONNECTIVE_RE.split(body) if len(p.strip()) > 3]
    if len(parts) >= 2:
        return [{"name": p[:80], "description": p} for p in parts]
    return []


def suggest_decomposition(pf: Any, ticket_id: str, *, max_subtasks: int = 6,
                          use_llm: bool = True) -> dict:
    """Propose an ordered, file-scoped subtask breakdown for a ticket. Tries the LLM when a
    model is configured; always falls back to the heuristic. Does NOT create tickets — feed
    the result into ``decompose.split_ticket``."""
    ticket = pf.get_ticket(ticket_id)
    if not ticket:
        raise ValueError(f"ticket {ticket_id} not found")
    subtasks, method = [], "heuristic"
    if use_llm and _llm_model():
        subtasks = _llm_subtasks(ticket, max_subtasks) or []
        if subtasks:
            method = "llm"
    if not subtasks:
        subtasks = heuristic_subtasks(ticket)
    return {"ticket": ticket_id, "method": method,
            "subtasks": subtasks[:max_subtasks], "atomic": not subtasks}


def _llm_subtasks(ticket: Any, max_subtasks: int) -> list[dict] | None:
    prompt = (
        "Break this engineering ticket into at most "
        f"{max_subtasks} smaller, independently-executable subtasks. Each subtask should touch "
        "a DISJOINT set of files so they never conflict, and be ordered if dependent. "
        'Return ONLY JSON: {"subtasks":[{"name":str,"description":str,"files":[str],"sequential":bool}]}.\n\n'
        f"TICKET: {ticket.name}\n\n{getattr(ticket, 'description', '') or ''}"
    )
    try:
        import json
        import litellm
        resp = litellm.completion(model=_llm_model(),
                                  messages=[{"role": "user", "content": prompt}],
                                  temperature=0.1, max_tokens=1500)
        content = resp.choices[0].message.content
        blob = content[content.index("{"):content.rindex("}") + 1]
        data = json.loads(blob)
        return [s for s in data.get("subtasks", []) if isinstance(s, dict) and s.get("name")]
    except Exception:  # noqa: BLE001 - degrade to heuristic
        return None


# ── 3. objective coverage of sprints / milestones ────────────────────────────

def coverage_report(pf: Any, *, sprint: str = "current", objectives: list[str] | None = None,
                    threshold: float = 0.5) -> dict:
    """Do the sprint's tickets semantically cover its objectives (milestones)? For each
    objective, find covering tickets (embed-cosine or lexical ≥ threshold). Reports covered
    objectives, their tickets, and the UNCOVERED objectives — the real gap in a plan."""
    tickets = list(pf.list_tickets(sprint=sprint))
    objs = objectives if objectives is not None else _sprint_objectives(pf, sprint)
    if not objs:
        return {"sprint": sprint, "objectives": 0, "covered": [], "uncovered": [],
                "method": "lexical", "coverage": 1.0, "note": "no objectives declared"}
    texts = [ticket_text(t) for t in tickets]
    vectors = embed_texts([*objs, *texts])
    method = "embed" if vectors else "lexical"
    obj_vecs = vectors[:len(objs)] if vectors else None
    tk_vecs = vectors[len(objs):] if vectors else None
    covered, uncovered = [], []
    for oi, obj in enumerate(objs):
        hits = _objective_hits(obj, oi, tickets, texts, obj_vecs, tk_vecs, threshold)
        (covered if hits else uncovered).append({"objective": obj, "tickets": hits} if hits else obj)
    pct = round(len(covered) / len(objs), 4)
    return {"sprint": sprint, "objectives": len(objs), "method": method, "threshold": threshold,
            "covered": covered, "uncovered": uncovered, "coverage": pct, "complete": not uncovered}


def _objective_hits(obj: str, oi: int, tickets: list, texts: list,
                    obj_vecs: Any, tk_vecs: Any, threshold: float) -> list[dict]:
    hits = []
    for ti, t in enumerate(tickets):
        score = cosine(obj_vecs[oi], tk_vecs[ti]) if obj_vecs else lexical_similarity(obj, texts[ti])
        if round(score, 4) >= threshold:
            hits.append({"id": t.id, "score": round(score, 4)})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits


def _sprint_objectives(pf: Any, sprint: str) -> list[str]:
    """Objectives declared on the sprint (strategy/planfile), best-effort."""
    try:
        data = pf.store.load_sprint(sprint) if sprint != "backlog" else pf.store.load_backlog()
        sd = data.get("sprint", data) if isinstance(data, dict) else {}
        objs = sd.get("objectives") or sd.get("goals") or []
        return [str(o) for o in objs if str(o).strip()]
    except Exception:  # noqa: BLE001
        return []
