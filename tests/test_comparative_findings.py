"""Tests for comparative improvement finding admission and ticket DAG persistence (PLF-20328)."""

from __future__ import annotations

from pathlib import Path

import pytest

from planfile import (
    ComparativeDependencyError,
    ComparativeFindingError,
    ComparativeFindingProposal,
    ObsoleteTargetHeadError,
    Planfile,
    admit_comparative_findings,
    compute_comparative_dedupe_key,
)
from planfile.core.store import TicketUpdatedAtConflictError


def _make_planfile(tmp_path: Path) -> Planfile:
    pf = Planfile(str(tmp_path))
    pf.store.init()
    return pf


def _sample_finding(
    finding_id: str = "FND-001",
    *,
    target_repository: str = "semcod/planfile",
    capability: str = "comparative-finding-dag-adapter",
    intent: str = "Admit comparative findings as idempotent ticket DAGs",
    policy_version: str = "v1",
    verdict: str = "actionable_gap",
    classification: str = "FEATURE",
    classification_reason: str = "Introduces the comparative finding lifecycle adapter",
    target_scope: list[str] | None = None,
    prerequisites: list[str] | None = None,
    parent_finding_id: str | None = None,
    parent_ticket_id: str | None = None,
    acceptance_test: list[str] | None = None,
    evidence_hash: str = "sha256:1111111111111111",
    target_head_sha: str = "e30c7e0fcc4629ddf49a55af549af2e5fbed23d5",
    evidence_fresh: bool = True,
    rollback: str = "Revert comparative_findings adapter module and API route",
    github_issue: dict | None = None,
    expected_updated_at: str | None = None,
) -> dict:
    return {
        "schema": "subactor.search/exemplar-gap-policy/v1",
        "finding_id": finding_id,
        "target_repository": target_repository,
        "capability": capability,
        "intent": intent,
        "policy_version": policy_version,
        "verdict": verdict,
        "classification": classification,
        "classification_reason": classification_reason,
        "target_scope": target_scope or ["planfile/core/comparative_findings.py"],
        "prerequisites": prerequisites or [],
        "parent_finding_id": parent_finding_id,
        "parent_ticket_id": parent_ticket_id,
        "acceptance_test": acceptance_test
        or ["pytest -q tests/test_comparative_findings.py"],
        "evidence_hash": evidence_hash,
        "target_head_sha": target_head_sha,
        "evidence_fresh": evidence_fresh,
        "rollback": rollback,
        "executor_ownership": {
            "kind": "llm",
            "mode": "automatic",
            "handler": "subactor/coding-agent",
            "workstream": "application",
            "queue": "default",
            "allocate_governance_ticket_after_admission": True,
        },
        "github_issue": github_issue,
        "expected_updated_at": expected_updated_at,
    }


def test_twice_imported_finding_and_refreshed_evidence_occurrence(tmp_path: Path):
    pf = _make_planfile(tmp_path)
    finding = _sample_finding(
        "FND-001",
        evidence_hash="sha256:aaaa1111",
        github_issue={"repository": "semcod/planfile", "issue": 301},
    )

    first = admit_comparative_findings(pf, [finding])
    assert first["admitted_count"] == 1
    d1 = first["decisions"][0]
    assert d1["outcome"] == "created"
    assert d1["mutated"] is True
    assert d1["occurrence_count"] == 1
    assert d1["governance_ticket_allocation"] == "deferred_until_post_admission"
    ticket_id = d1["ticket_id"]

    # 1. Re-importing the exact same finding and evidence hash is a no-op duplicate
    second = admit_comparative_findings(pf, [finding])
    d2 = second["decisions"][0]
    assert d2["ticket_id"] == ticket_id
    assert d2["outcome"] == "deduplicated_unchanged"
    assert d2["mutated"] is False
    assert d2["occurrence_count"] == 1
    assert len(pf.list_tickets(sprint="all")) == 1

    # 2. Re-importing with a refreshed evidence hash appends an occurrence on the same ticket
    refreshed = _sample_finding(
        "FND-001-REFRESH",
        evidence_hash="sha256:bbbb2222",
        target_head_sha="a7f9e7c01599066f59a61263c7ac1c6fe050475a",
        github_issue={"repository": "semcod/planfile", "issue": 301},
    )
    third = admit_comparative_findings(pf, [refreshed])
    d3 = third["decisions"][0]
    assert d3["ticket_id"] == ticket_id
    assert d3["outcome"] == "occurrence_appended"
    assert d3["mutated"] is True
    assert d3["occurrence_count"] == 2
    assert len(pf.list_tickets(sprint="all")) == 1

    stored = pf.get_ticket(ticket_id)
    assert stored is not None
    assert stored.sync["github"]["issue"] == 301
    assert stored.outputs.result["occurrence_count"] == 2
    assert [
        occ["evidence_hash"]
        for occ in stored.outputs.result["comparative_occurrences"]
    ] == ["sha256:aaaa1111", "sha256:bbbb2222"]


def test_materially_changed_requirements_produce_distinct_tickets(tmp_path: Path):
    pf = _make_planfile(tmp_path)
    base = _sample_finding("FND-BASE", target_scope=["planfile/core/a.py"])
    changed_scope = _sample_finding("FND-SCOPE", target_scope=["planfile/core/b.py"])
    changed_class = _sample_finding("FND-BUG", classification="BUGFIX")

    p_base = ComparativeFindingProposal.model_validate(base)
    p_scope = ComparativeFindingProposal.model_validate(changed_scope)
    p_class = ComparativeFindingProposal.model_validate(changed_class)

    assert compute_comparative_dedupe_key(p_base) != compute_comparative_dedupe_key(p_scope)
    assert compute_comparative_dedupe_key(p_base) != compute_comparative_dedupe_key(p_class)

    report = admit_comparative_findings(pf, [base, changed_scope, changed_class])
    ticket_ids = [d["ticket_id"] for d in report["decisions"]]
    assert len(set(ticket_ids)) == 3


def test_concurrent_refresh_respects_expected_updated_at_cas(tmp_path: Path):
    pf = _make_planfile(tmp_path)
    initial = _sample_finding("FND-CAS", evidence_hash="sha256:1111")
    report = admit_comparative_findings(pf, [initial])
    ticket_id = report["decisions"][0]["ticket_id"]
    original_ticket = pf.get_ticket(ticket_id)
    assert original_ticket is not None
    stale_updated_at = original_ticket.updated_at.isoformat()

    # Simulate a concurrent writer updating the ticket before our refresh arrives
    pf.update_ticket(
        ticket_id,
        priority="high",
        reason="concurrent_operator_edit",
        actor="operator:test",
    )

    stale_refresh = _sample_finding(
        "FND-CAS",
        evidence_hash="sha256:2222",
        expected_updated_at=stale_updated_at,
    )
    with pytest.raises(TicketUpdatedAtConflictError):
        admit_comparative_findings(pf, [stale_refresh])

    # Refresh with current expected_updated_at succeeds
    latest = pf.get_ticket(ticket_id)
    assert latest is not None
    fresh_refresh = _sample_finding(
        "FND-CAS",
        evidence_hash="sha256:2222",
        expected_updated_at=latest.updated_at.isoformat(),
    )
    refreshed_report = admit_comparative_findings(pf, [fresh_refresh])
    assert refreshed_report["decisions"][0]["outcome"] == "occurrence_appended"


def test_obsolete_target_head_and_stale_evidence_rejected_without_mutation(tmp_path: Path):
    pf = _make_planfile(tmp_path)
    finding = _sample_finding(
        "FND-STALE-HEAD",
        target_repository="semcod/planfile",
        target_head_sha="1111111111111111111111111111111111111111",
    )
    with pytest.raises(ObsoleteTargetHeadError, match="obsolete_target_head"):
        admit_comparative_findings(
            pf,
            [finding],
            current_target_heads={
                "semcod/planfile": "e30c7e0fcc4629ddf49a55af549af2e5fbed23d5"
            },
        )
    assert pf.list_tickets(sprint="all") == []

    unfresh = _sample_finding("FND-UNFRESH", evidence_fresh=False)
    with pytest.raises(ObsoleteTargetHeadError, match="obsolete_target_evidence"):
        admit_comparative_findings(pf, [unfresh])
    assert pf.list_tickets(sprint="all") == []


def test_terminal_ticket_recurrence_creates_linked_successor(tmp_path: Path):
    pf = _make_planfile(tmp_path)
    finding = _sample_finding("FND-RECUR", evidence_hash="sha256:first")
    first = admit_comparative_findings(pf, [finding])
    first_id = first["decisions"][0]["ticket_id"]

    # Complete the first ticket so it transitions to terminal 'done'
    pf.complete_ticket(first_id, reason="resolved_initial_occurrence", actor="agent:test")
    completed = pf.get_ticket(first_id)
    assert completed is not None
    assert str(completed.status.value) == "done"

    # Re-admitting the recurring finding creates a new ticket linked to first_id
    recurring = _sample_finding("FND-RECUR-2", evidence_hash="sha256:second")
    second = admit_comparative_findings(pf, [recurring])
    d2 = second["decisions"][0]
    assert d2["outcome"] == "recurrence_created"
    assert d2["ticket_id"] != first_id
    assert d2["recurs_from_ticket_id"] == first_id

    successor = pf.get_ticket(d2["ticket_id"])
    assert successor is not None
    assert f"recurs-from:{first_id}" in successor.labels
    assert successor.source.context["recurs_from_ticket_id"] == first_id
    # Original terminal ticket remains 'done'
    assert str(pf.get_ticket(first_id).status.value) == "done"


def test_dag_relationships_layers_and_cycle_or_dependency_failures(tmp_path: Path):
    pf = _make_planfile(tmp_path)
    parent = _sample_finding(
        "FND-EPIC",
        capability="epic-capability",
        intent="Coordinate multi-step comparative remediation",
        prerequisites=["FND-STEP-1", "FND-STEP-2"],
    )
    step1 = _sample_finding(
        "FND-STEP-1",
        capability="step-1",
        intent="Deliver foundation slice",
        parent_finding_id="FND-EPIC",
    )
    step2 = _sample_finding(
        "FND-STEP-2",
        capability="step-2",
        intent="Deliver dependent slice",
        prerequisites=["FND-STEP-1"],
        parent_finding_id="FND-EPIC",
    )

    report = admit_comparative_findings(pf, [parent, step1, step2])
    assert report["dag_valid"] is True
    by_fnd = {d["finding_id"]: d for d in report["decisions"]}
    epic_id = by_fnd["FND-EPIC"]["ticket_id"]
    s1_id = by_fnd["FND-STEP-1"]["ticket_id"]
    s2_id = by_fnd["FND-STEP-2"]["ticket_id"]

    epic_ticket = pf.get_ticket(epic_id)
    s1_ticket = pf.get_ticket(s1_id)
    s2_ticket = pf.get_ticket(s2_id)
    assert epic_ticket is not None and s1_ticket is not None and s2_ticket is not None

    assert set(epic_ticket.children) == {s1_id, s2_id}
    assert set(epic_ticket.blocked_by) == {s1_id, s2_id}
    assert s1_ticket.parent == epic_id
    assert s2_ticket.parent == epic_id
    assert s2_ticket.blocked_by == [s1_id]
    assert s2_id in s1_ticket.blocks
    assert report["execution_layers"] == [[s1_id], [s2_id], [epic_id]]

    # Cyclic findings are rejected before any ticket allocation
    cyc_a = _sample_finding("FND-CYC-A", capability="cyc-a", prerequisites=["FND-CYC-B"])
    cyc_b = _sample_finding("FND-CYC-B", capability="cyc-b", prerequisites=["FND-CYC-A"])
    with pytest.raises(ComparativeDependencyError, match="cycle"):
        admit_comparative_findings(pf, [cyc_a, cyc_b])

    # Dependency on a failed ticket is rejected fail-closed
    failed_prereq = pf.create_ticket("Failed prerequisite")
    pf.fail_ticket(failed_prereq.id, error="build_failed", reason="ci_failed", actor="ci")
    dep_on_failed = _sample_finding(
        "FND-DEP-FAIL",
        capability="dep-fail",
        prerequisites=[failed_prereq.id],
    )
    with pytest.raises(ComparativeDependencyError, match="prerequisite_in_failed_state"):
        admit_comparative_findings(pf, [dep_on_failed])


def test_no_change_dry_run_and_governance_ticket_deferral_guard(tmp_path: Path):
    pf = _make_planfile(tmp_path)
    no_change = _sample_finding(
        "FND-NO-CHANGE",
        verdict="intentional_difference_preserved",
    )
    actionable = _sample_finding("FND-DRY", capability="dry-cap")

    dry_report = admit_comparative_findings(
        pf,
        [no_change, actionable],
        dry_run=True,
    )
    assert dry_report["dry_run"] is True
    assert dry_report["admitted_count"] == 1
    assert dry_report["no_change_count"] == 1
    assert pf.list_tickets(sprint="all") == []

    # Pre-allocated governance ticket before admission is rejected
    preallocated = _sample_finding("FND-PREALLOC")
    preallocated["executor_ownership"]["preallocated_governance_ticket"] = "ticket-999"
    with pytest.raises(
        ComparativeFindingError,
        match="governance_ticket_must_be_allocated_after_admission",
    ):
        admit_comparative_findings(pf, [preallocated])


def test_rest_api_persists_dag_fields_and_admits_comparative_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pytest.importorskip("fastapi")
    from starlette.testclient import TestClient

    from planfile.api import server

    pf = _make_planfile(tmp_path)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setenv("PLANFILE_REQUIRE_PROCESS_ENVELOPE", "0")
    client = TestClient(server.app)

    # 1. Create parent and prerequisite via POST /tickets with real DAG fields
    r_parent = client.post(
        "/tickets",
        json={"name": "Parent Epic", "group": "comparative-epic"},
    )
    assert r_parent.status_code == 201
    parent_id = r_parent.json()["id"]

    r_prereq = client.post(
        "/tickets",
        json={"name": "Prerequisite Slice", "parent": parent_id},
    )
    assert r_prereq.status_code == 201
    prereq_id = r_prereq.json()["id"]
    assert r_prereq.json()["parent"] == parent_id

    r_child = client.post(
        "/tickets",
        json={
            "name": "Dependent Slice",
            "parent": parent_id,
            "blocked_by": [prereq_id],
            "acceptance_criteria": ["pytest -q"],
            "files": ["planfile/core/comparative_findings.py"],
        },
    )
    assert r_child.status_code == 201
    child_data = r_child.json()
    child_id = child_data["id"]
    assert child_data["blocked_by"] == [prereq_id]
    assert child_data["parent"] == parent_id

    # 2. Update parent children via PATCH /tickets/{id} and reject cycle
    r_patch = client.patch(
        f"/tickets/{parent_id}",
        json={"children": [prereq_id, child_id]},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["children"] == [prereq_id, child_id]

    r_cycle = client.patch(
        f"/tickets/{prereq_id}",
        json={"blocked_by": [child_id]},
    )
    assert r_cycle.status_code == 409
    assert "dependency_cycle_detected" in r_cycle.json()["detail"]

    # 3. Admit comparative findings via POST /findings/comparative/admit
    finding = _sample_finding(
        "FND-API-1",
        prerequisites=[child_id],
        parent_ticket_id=parent_id,
    )
    r_admit = client.post(
        "/findings/comparative/admit",
        json={
            "findings": [finding],
            "current_target_heads": {
                "semcod/planfile": "e30c7e0fcc4629ddf49a55af549af2e5fbed23d5"
            },
        },
    )
    assert r_admit.status_code == 200
    body = r_admit.json()
    assert body["admitted_count"] == 1
    admitted_id = body["decisions"][0]["ticket_id"]
    admitted_ticket = pf.get_ticket(admitted_id)
    assert admitted_ticket is not None
    assert admitted_ticket.blocked_by == [child_id]
    assert admitted_ticket.parent == parent_id
