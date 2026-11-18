"""Tests for bounded and atomic API DAG dependency validation (ticket-291 / #328)."""

from __future__ import annotations

import sqlite3
import threading
import time

from fastapi.testclient import TestClient

from planfile import Planfile, Ticket
from planfile.api import server as api_server
from planfile.core import fastio
from planfile.core.sqlite_index import SQLiteTicketIndex


def _make_ticket(
    ticket_id: str,
    *,
    name: str,
    sprint: str = "current",
    status: str = "open",
    description: str = "",
    blocked_by: list[str] | None = None,
    outputs: dict | None = None,
) -> Ticket:
    return Ticket(
        id=ticket_id,
        name=name,
        sprint=sprint,
        status=status,
        description=description,
        blocked_by=list(blocked_by or []),
        outputs=outputs,
    )


def test_single_dag_mutation_skips_archive_descriptions_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANFILE_DISABLE_INDEX_MAINTENANCE", "1")
    pf = Planfile(tmp_path)
    pf.store.configure_ticket_index(True)

    archived_payload = "A" * 4096
    bulk = [
        _make_ticket(
            f"PLF-{idx:03d}",
            name=f"Archived task {idx}",
            sprint="sprint-archive-1" if idx <= 100 else "sprint-archive-2",
            status="done",
            description=archived_payload,
            outputs={"artifacts": [f"artifact-{idx}.bin"], "notes": [archived_payload]},
        )
        for idx in range(1, 201)
    ]
    bulk.extend(
        [
            _make_ticket("PLF-201", name="Root node", sprint="current"),
            _make_ticket("PLF-202", name="Middle node", sprint="current", blocked_by=["PLF-201"]),
            _make_ticket("PLF-203", name="Leaf node", sprint="current"),
        ]
    )
    pf.store.create_tickets_bulk(bulk)
    pf.store.ensure_ticket_index(force=True)

    monkeypatch.setattr(api_server, "get_planfile", lambda: pf)
    monkeypatch.setattr(
        pf,
        "list_tickets",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("full list_tickets forbidden")),
    )

    archive_yaml_reads: list[str] = []
    orig_read_yaml = fastio.read_yaml_fast

    def counting_read_yaml(path, *args, **kwargs):
        if "sprint-archive-" in str(path):
            archive_yaml_reads.append(str(path))
        return orig_read_yaml(path, *args, **kwargs)

    monkeypatch.setattr(fastio, "read_yaml_fast", counting_read_yaml)

    dag_calls: list[dict] = []
    orig_dag_snapshot = SQLiteTicketIndex.dag_snapshot

    def spying_dag_snapshot(self, signature, *, references=(), subject_id=None):
        result = orig_dag_snapshot(self, signature, references=references, subject_id=subject_id)
        dag_calls.append({"source": result["source"], "subject_id": subject_id})
        return result

    monkeypatch.setattr(SQLiteTicketIndex, "dag_snapshot", spying_dag_snapshot)

    client = TestClient(api_server.app)
    started = time.monotonic()
    ok_res = client.patch("/tickets/PLF-203", json={"blocked_by": ["PLF-202"]})
    cycle_res = client.patch("/tickets/PLF-201", json={"blocked_by": ["PLF-203"]})
    elapsed = time.monotonic() - started

    assert ok_res.status_code == 200, ok_res.text
    assert ok_res.headers.get("X-Planfile-Mutation-Stage") == "committed"
    assert cycle_res.status_code == 409, cycle_res.text
    assert "dependency_cycle_detected" in cycle_res.json()["detail"]
    assert cycle_res.headers.get("X-Planfile-Mutation-Stage") == "dag_validation"
    assert archive_yaml_reads == []
    assert [c["source"] for c in dag_calls] == ["sqlite_index", "sqlite_index"]
    assert elapsed < 2.0


def test_concurrent_opposing_edges_never_admit_cycle(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANFILE_DISABLE_INDEX_MAINTENANCE", "1")
    pf = Planfile(tmp_path)
    pf.store.configure_ticket_index(True)
    pf.store.create_tickets_bulk(
        [
            _make_ticket("PLF-001", name="Node A", sprint="current"),
            _make_ticket("PLF-002", name="Node B", sprint="current"),
            _make_ticket("PLF-003", name="Node C", sprint="current"),
            _make_ticket("PLF-004", name="Node D", sprint="current"),
        ]
    )
    pf.store.ensure_ticket_index(force=True)
    monkeypatch.setattr(api_server, "get_planfile", lambda: pf)

    pairs = [("PLF-001", "PLF-002"), ("PLF-003", "PLF-004")]
    for left, right in pairs:
        barrier = threading.Barrier(2)
        outcomes: list[int] = []
        outcome_lock = threading.Lock()

        def worker(
            subject: str,
            dep: str,
            sync_barrier: threading.Barrier = barrier,
            results: list[int] = outcomes,
            results_lock: threading.Lock = outcome_lock,
        ) -> None:
            client = TestClient(api_server.app)
            sync_barrier.wait(timeout=5)
            resp = client.patch(f"/tickets/{subject}", json={"blocked_by": [dep]})
            with results_lock:
                results.append(resp.status_code)

        t1 = threading.Thread(target=worker, args=(left, right))
        t2 = threading.Thread(target=worker, args=(right, left))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
        assert sorted(outcomes) == [200, 409]

    # Also test POST /tickets(blocks=[...]) racing PATCH blocked_by against a fresh seed.
    seed = pf.store.create_ticket(_make_ticket("PLF-005", name="Node E", sprint="current"))
    barrier = threading.Barrier(2)
    mixed_statuses: list[int] = []
    mixed_lock = threading.Lock()

    def creator() -> None:
        client = TestClient(api_server.app)
        barrier.wait(timeout=5)
        resp = client.post(
            "/tickets",
            json={
                "name": "Concurrent new blocker",
                "sprint": "current",
                "blocked_by": [seed.id],
                "blocks": [seed.id],
            },
        )
        with mixed_lock:
            mixed_statuses.append(resp.status_code)

    def patcher() -> None:
        client = TestClient(api_server.app)
        barrier.wait(timeout=5)
        resp = client.patch(f"/tickets/{seed.id}", json={"description": "concurrent note"})
        with mixed_lock:
            mixed_statuses.append(resp.status_code)

    tc = threading.Thread(target=creator)
    tp = threading.Thread(target=patcher)
    tc.start()
    tp.start()
    tc.join(timeout=10)
    tp.join(timeout=10)
    assert sorted(mixed_statuses) == [200, 409]

    is_dag, cycle_nodes = pf.validate_dependencies(sprint="all")
    assert is_dag is True
    assert cycle_nodes == []


def test_missing_or_stale_index_bounded_fallback_and_typed_503_refusal(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANFILE_DISABLE_INDEX_MAINTENANCE", "1")
    pf = Planfile(tmp_path)
    pf.store.configure_ticket_index(True)
    pf.store.create_tickets_bulk(
        [
            _make_ticket("PLF-001", name="One", sprint="current"),
            _make_ticket("PLF-002", name="Two", sprint="current", blocked_by=["PLF-001"]),
        ]
    )
    index_path = pf.store._sqlite_ticket_index().path
    if index_path.exists():
        index_path.unlink()

    monkeypatch.setattr(api_server, "get_planfile", lambda: pf)
    client = TestClient(api_server.app)

    # Small store with missing SQLite index still detects cycles via bounded record scan.
    cycle_small = client.patch("/tickets/PLF-001", json={"blocked_by": ["PLF-002"]})
    assert cycle_small.status_code == 409, cycle_small.text
    assert "dependency_cycle_detected" in cycle_small.json()["detail"]
    assert cycle_small.headers.get("X-Planfile-Mutation-Stage") == "dag_validation"

    # Grow store beyond PLANFILE_DAG_FALLBACK_MAX_BYTES with missing/stale index -> typed 503.
    big_desc = "X" * 1024
    pf.store.create_tickets_bulk(
        [
            _make_ticket(
                f"PLF-{idx:03d}",
                name=f"Archive {idx}",
                sprint="sprint-archive",
                status="done",
                description=big_desc,
            )
            for idx in range(10, 25)
        ]
    )
    if index_path.exists():
        index_path.unlink()
    monkeypatch.setenv("PLANFILE_DAG_FALLBACK_MAX_BYTES", "1024")

    refused = client.patch("/tickets/PLF-001", json={"blocked_by": ["PLF-002"]})
    assert refused.status_code == 503, refused.text
    body = refused.json()
    assert body["code"] == "dag_validation_index_unavailable"
    assert body["stage"] == "dag_validation"
    assert body["retryable"] is True
    assert refused.headers.get("Retry-After") == str(api_server.STORE_LOCK_RETRY_AFTER_SECONDS)
    assert refused.headers.get("X-Planfile-Mutation-Stage") == "dag_validation"
    assert pf.get_ticket("PLF-001", repair_index=False).blocked_by == []

    # After explicit repair, valid mutation succeeds and cycles remain rejected.
    api_server._repair_ticket_index()
    repaired_cycle = client.patch("/tickets/PLF-001", json={"blocked_by": ["PLF-002"]})
    assert repaired_cycle.status_code == 409
    assert "dependency_cycle_detected" in repaired_cycle.json()["detail"]


def test_post_commit_timeout_idempotency_cas_readback_and_stage_diagnostics(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PLANFILE_DISABLE_INDEX_MAINTENANCE", "1")
    pf = Planfile(tmp_path)
    pf.store.configure_ticket_index(True)
    seed = pf.store.create_ticket(_make_ticket("PLF-001", name="Seed", sprint="current"))
    pf.store.ensure_ticket_index(force=True)
    monkeypatch.setattr(api_server, "get_planfile", lambda: pf)
    client = TestClient(api_server.app)

    # Deduplicated retry after a simulated response timeout returns committed ticket cleanly.
    dedupe_payload = {
        "name": "DAG task",
        "sprint": "current",
        "blocked_by": [seed.id],
        "dedupe_key": "uri-reuse-20261031:semcod/planfile:PLF-21690",
    }
    first = client.post("/tickets", json=dedupe_payload)
    retry = client.post("/tickets", json=dedupe_payload)
    assert first.status_code == 201, first.text
    assert first.headers.get("X-Planfile-Mutation-Stage") == "committed"
    assert retry.status_code == 200, retry.text
    assert retry.headers.get("X-Planfile-Mutation-Stage") == "deduplicated_readback"
    created_id = first.json()["id"]
    assert retry.json()["id"] == created_id

    # CAS retry with pre-commit updated_at fails cleanly at canonical_write while GET shows commit.
    target_before = pf.get_ticket(seed.id, repair_index=False)
    expected_updated_at = target_before.model_dump(mode="json")["updated_at"]
    cas_ok = client.post(
        f"/tickets/{seed.id}/update-if-current",
        json={
            "description": "cas updated",
            "expected_updated_at": expected_updated_at,
        },
    )
    cas_retry = client.post(
        f"/tickets/{seed.id}/update-if-current",
        json={
            "description": "cas updated",
            "expected_updated_at": expected_updated_at,
        },
    )
    assert cas_ok.status_code == 200, cas_ok.text
    assert cas_ok.headers.get("X-Planfile-Mutation-Stage") == "committed"
    assert cas_retry.status_code == 409, cas_retry.text
    assert cas_retry.json()["detail"] == "ticket_updated_at_precondition_failed"
    assert cas_retry.headers.get("X-Planfile-Mutation-Stage") == "canonical_write"

    # Derived-index failure after canonical commit succeeds with explicit degraded diagnostics.
    third = pf.store.create_ticket(_make_ticket("PLF-003", name="Third", sprint="current"))
    pf.store.ensure_ticket_index(force=True)

    def broken_apply(self, **_kwargs):
        raise sqlite3.DatabaseError("simulated derived index failure")

    monkeypatch.setattr(SQLiteTicketIndex, "apply", broken_apply)
    degraded = client.patch(f"/tickets/{seed.id}", json={"blocked_by": [third.id]})
    assert degraded.status_code == 200, degraded.text
    assert degraded.headers.get("X-Planfile-Mutation-Stage") == "derived_index_degraded"
    assert degraded.headers.get("X-Planfile-Index-State") == "degraded"
    assert degraded.json()["blocked_by"] == [third.id]
    assert pf.get_ticket(seed.id, repair_index=False).blocked_by == [third.id]
