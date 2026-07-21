from __future__ import annotations

from hashlib import sha256

import pytest
from filelock import Timeout as FileLockTimeout
from pydantic import ValidationError

from planfile import Planfile
from planfile.client import PlanfileClient
from planfile.contracts import TicketProposalV1


def _proposal(**overrides) -> TicketProposalV1:
    payload = {
        "schema": "planfile.ticket-proposal.v1",
        "proposal_id": "code2llm:src/example.py:Example",
        "dedupe_key": "symbol:src/example.py:Example",
        "name": "Split Example",
        "description": "The class combines unrelated responsibilities.",
        "priority": "high",
        "source": {
            "tool": "code2llm",
            "tool_version": "0.9.0",
            "finding_id": "src/example.py:Example",
            "artifact_digest": "sha256:" + "a" * 64,
        },
        "labels": ["refactor", "analysis", "refactor"],
        "files": ["src/example.py", "src/example.py"],
        "acceptance_criteria": ["Tests pass", "Tests pass", "Class is split"],
        "evidence_refs": ["analysis.json#L10"],
    }
    payload.update(overrides)
    return TicketProposalV1.model_validate(payload)


def test_ticket_proposal_is_canonical_and_hash_bound() -> None:
    first = _proposal()
    second = _proposal(labels=["analysis", "refactor"], files=["src/example.py"])

    assert first.canonical_json() == second.canonical_json()
    assert first.proposal_hash == sha256(first.canonical_json().encode()).hexdigest()
    assert first.labels == ("analysis", "refactor")
    assert first.acceptance_criteria == ("Tests pass", "Class is split")


def test_ticket_proposal_rejects_execution_authority() -> None:
    with pytest.raises(ValidationError):
        _proposal(capability="repo.promote_main")
    with pytest.raises(ValidationError):
        _proposal(executor={"kind": "shell", "handler": "rm -rf project"})


def test_ticket_proposal_converts_only_safe_ticket_fields() -> None:
    kwargs = _proposal().to_ticket_kwargs()

    assert set(kwargs) == {
        "acceptance_criteria",
        "description",
        "files",
        "labels",
        "name",
        "priority",
        "source",
    }
    assert kwargs["source"].tool == "code2llm"
    assert kwargs["source"].context["proposal_hash"]


def test_planfile_client_returns_typed_transition_results(tmp_path) -> None:
    backend = Planfile(str(tmp_path))
    ticket = backend.create_ticket(name="Typed lifecycle")
    client = PlanfileClient(backend=backend)

    started = client.start(ticket.id, assigned_to="koru", actor="koru")
    noted = client.note(ticket.id, "Evidence attached", actor="koru")
    completed = client.complete(ticket.id, actor="koru")
    missing = client.block("PLF-404", reason="missing")

    assert started.code == "ok"
    assert started.ticket["execution"]["state"] == "running"
    assert noted.code == "ok"
    assert noted.ticket["outputs"]["notes"] == ["Evidence attached"]
    assert completed.code == "ok"
    assert completed.ticket["status"] == "done"
    assert missing.code == "ticket_not_found"
    assert not missing.retryable
    assert missing.model_dump(by_alias=True)["schema"] == (
        "planfile.ticket-transition-result.v1"
    )


def test_planfile_client_exposes_failure_and_explicit_retry(tmp_path) -> None:
    backend = Planfile(str(tmp_path))
    ticket = backend.create_ticket(name="Retryable lifecycle")
    client = PlanfileClient(backend=backend)

    assert client.start(ticket.id, assigned_to="koru").code == "ok"
    failed = client.fail(ticket.id, error="temporary failure", actor="koru")
    ready = client.ready(ticket.id, note="Retry 2/3 scheduled", actor="koru")

    assert failed.code == "ok"
    assert failed.ticket["execution"]["state"] == "failed"
    assert failed.ticket["execution"]["attempt"] == 1
    assert ready.code == "ok"
    assert ready.ticket["status"] == "open"
    assert ready.ticket["execution"]["state"] == "ready"
    assert ready.ticket["execution"]["attempt"] == 1
    assert ready.ticket["outputs"]["notes"] == ["Retry 2/3 scheduled"]


class _LockingBackend:
    calls = 0

    def start_ticket(self, *_args, **_kwargs):
        self.calls += 1
        raise FileLockTimeout("tickets.lock")


def test_planfile_client_owns_bounded_lock_retry() -> None:
    backend = _LockingBackend()
    sleeps: list[float] = []
    client = PlanfileClient(
        backend=backend,  # type: ignore[arg-type]
        lock_retry_attempts=3,
        lock_retry_delay_seconds=0.1,
        sleep=sleeps.append,
    )

    result = client.start("PLF-1")

    assert result.code == "lock_timeout"
    assert result.retryable
    assert result.attempts == 3
    assert backend.calls == 3
    assert sleeps == [0.1, 0.2]


class _InvalidBackend:
    def block_ticket(self, *_args, **_kwargs):
        raise ValueError("invalid transition")


def test_planfile_client_maps_domain_errors_without_text_matching() -> None:
    client = PlanfileClient(backend=_InvalidBackend())  # type: ignore[arg-type]

    result = client.block("PLF-1")

    assert result.code == "invalid_transition"
    assert not result.retryable
