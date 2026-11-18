"""Tests for v2 verified repository placement and multi-repo delivery bundles (#383)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from planfile import (
    COMPILED_WORK_PLAN_V2_SCHEMA,
    DELIVERY_PLACEMENT_V2_SCHEMA,
    DELIVERY_PLAN_BUNDLE_SCHEMA,
    CompiledWorkPlanV1,
    CompiledWorkPlanV2,
    DeliveryPlanBundleV1,
    DeliveryPlanError,
    Planfile,
    compose_delivery_plan_bundle,
)
from planfile.api import server
from planfile.delivery_plan_contracts import (
    TICKET_CANDIDATE_V2_SCHEMA,
    preflight_delivery_plan_payload,
)

PLAN_HASH = "sha256:" + "a" * 64


def _digest(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _v2_placement(home: str, *, runtime_owner: str | None = None, shape: str = "runtime_service") -> dict:
    return {
        "schema": DELIVERY_PLACEMENT_V2_SCHEMA,
        "home": home,
        "shape": shape,
        "runtime_owner": runtime_owner or home,
        "adopt": ["wellmanifest/dsl", "wellmanifest/new-project"],
    }


def _v2_candidate(
    key: str,
    order: int,
    *,
    home: str,
    plan_hash: str = PLAN_HASH,
    depends_on: list[str] | None = None,
    external_depends_on: list[dict] | None = None,
    runtime_owner: str | None = None,
) -> dict:
    placement = _v2_placement(home, runtime_owner=runtime_owner)
    ext = sorted(external_depends_on or [], key=lambda d: (d["plan_id"], d["candidate_key"]))
    core = {
        "schema": TICKET_CANDIDATE_V2_SCHEMA,
        "plan_hash": plan_hash,
        "candidate_key": key,
        "order": order,
        "title": f"Deliver {home} {key}",
        "workstream": "application",
        "depends_on": sorted(depends_on or []),
        "external_depends_on": ext,
        "allowed_paths": [f"src/{key}.py"],
        "placement": placement,
        "delivery": {
            "complexity": "S",
            "estimated_minutes": 20,
            "max_implementation_files": 2,
            "max_affected_components": 1,
            "max_public_interface_changes": 0,
            "max_runtime_dependencies": 0,
        },
        "components": ["delivery-plan"],
        "public_interfaces": [],
        "runtime_dependencies": [],
        "acceptance": [
            {
                "id": "AC-01",
                "statement": "Verified slice check.",
                "test_ids": ["python-suite"],
            }
        ],
        "tests": [
            {"id": "python-suite", "kind": "python-test", "target": "tests/test_delivery_plan.py"}
        ],
        "execution": "inert",
    }
    digest = _digest(core)
    return {
        **core,
        "candidate_digest": digest,
        "idempotency_key": _digest(
            {"plan_hash": plan_hash, "candidate_key": key, "candidate_digest": digest}
        ),
        "state": "pending",
        "split_reasons": [],
        "terminal_receipt_ref": None,
    }


def _v2_plan(
    *,
    plan_id: str,
    repository: str,
    home: str,
    base_sha: str,
    candidates: list[dict],
    plan_hash: str = PLAN_HASH,
    runtime_owner: str | None = None,
) -> dict:
    return {
        "schema": COMPILED_WORK_PLAN_V2_SCHEMA,
        "status": "ready",
        "execution": "inert",
        "authority": "none",
        "plan_id": plan_id,
        "plan_ref": f"artifact://{repository}/{plan_id}",
        "plan_hash": plan_hash,
        "repository": repository,
        "accepted_base_sha": base_sha,
        "target_branch": "main",
        "placement": _v2_placement(home, runtime_owner=runtime_owner),
        "candidate_count": len(candidates),
        "pending_count": len(candidates),
        "split_required": [],
        "terminal_candidates": [],
        "candidates": candidates,
    }


def _proposal(
    proposal_key: str,
    *,
    repository: str,
    home: str,
    base_sha: str,
    depends_on: list[str] | None = None,
) -> dict:
    return {
        "proposal_key": proposal_key,
        "repository": repository,
        "accepted_base_sha": base_sha,
        "placement": _v2_placement(home),
        "title": f"{repository} :: {proposal_key}",
        "workstream": "application",
        "depends_on_proposals": list(depends_on or []),
        "allowed_paths": [f"src/{proposal_key}.py"],
        "delivery": {
            "complexity": "S",
            "estimated_minutes": 20,
            "max_implementation_files": 2,
            "max_affected_components": 1,
            "max_public_interface_changes": 0,
            "max_runtime_dependencies": 0,
        },
        "components": ["bundle-slice"],
        "acceptance": [
            {
                "id": "AC-01",
                "statement": f"Verify {proposal_key}",
                "test_ids": ["py-suite"],
            }
        ],
        "tests": [
            {
                "id": "py-suite",
                "kind": "python-test",
                "target": "tests/test_delivery_plan_multi_repo_bundle.py",
            }
        ],
    }


def test_v2_accepts_verified_trusted_targets_and_refuses_untrusted_before_write(tmp_path) -> None:
    pf = Planfile(str(tmp_path))

    autodo_plan = _v2_plan(
        plan_id="autodo-trusted-v2",
        repository="uritime/autodo",
        home="uritime",
        base_sha="1" * 40,
        candidates=[_v2_candidate("auto-core", 0, home="uritime")],
    )
    heyasa_plan = _v2_plan(
        plan_id="heyasa-trusted-v2",
        repository="paxlet-com/heyasa",
        home="paxlet-com",
        base_sha="2" * 40,
        candidates=[_v2_candidate("hey-core", 0, home="paxlet-com")],
    )

    assert preflight_delivery_plan_payload(autodo_plan)["ok"] is True
    assert preflight_delivery_plan_payload(heyasa_plan)["ok"] is True
    s_auto = pf.materialize_delivery_plan(autodo_plan)
    s_hey = pf.materialize_delivery_plan(heyasa_plan)
    assert s_auto["repository"] == "uritime/autodo"
    assert s_auto["accepted_base_sha"] == "1" * 40
    assert s_auto["placement"]["home"] == "uritime"
    assert s_hey["repository"] == "paxlet-com/heyasa"
    assert s_hey["placement"]["home"] == "paxlet-com"

    # Reject unknown repository / unverified org repo / runtime owner / owner aliasing.
    untrusted_repo = _v2_plan(
        plan_id="untrusted-plan",
        repository="rogue-org/tool",
        home="rogue-org",
        base_sha="3" * 40,
        candidates=[_v2_candidate("bad-slice", 0, home="rogue-org")],
    )
    assert CompiledWorkPlanV2.model_validate(untrusted_repo)  # shape valid != permission!
    untrusted_pre = preflight_delivery_plan_payload(untrusted_repo)
    assert untrusted_pre["ok"] is False
    assert untrusted_pre["code"] == "delivery_plan_target_not_trusted"

    unverified_uritime = _v2_plan(
        plan_id="unverified-uritime",
        repository="uritime/unlisted-repo",
        home="uritime",
        base_sha="3" * 40,
        candidates=[_v2_candidate("bad-slice", 0, home="uritime")],
    )
    assert preflight_delivery_plan_payload(unverified_uritime)["code"] == "delivery_plan_target_not_trusted"

    aliased_owner = _v2_plan(
        plan_id="aliased-owner",
        repository="uritime/autodo",
        home="semcod",
        base_sha="3" * 40,
        candidates=[_v2_candidate("bad-slice", 0, home="semcod")],
    )
    with pytest.raises(ValidationError, match="delivery_plan_owner_namespace_mismatch"):
        CompiledWorkPlanV2.model_validate(aliased_owner)

    bad_runtime_owner = _v2_plan(
        plan_id="bad-runtime",
        repository="uritime/autodo",
        home="uritime",
        runtime_owner="rogue-runner",
        base_sha="3" * 40,
        candidates=[_v2_candidate("bad-slice", 0, home="uritime", runtime_owner="rogue-runner")],
    )
    with pytest.raises(DeliveryPlanError, match="delivery_plan_runtime_owner_not_trusted"):
        pf.materialize_delivery_plan(bad_runtime_owner)

    with pytest.raises(DeliveryPlanError, match="delivery_plan_target_not_trusted"):
        pf.materialize_delivery_plan(untrusted_repo)
    # Failed pre-write target checks did not write extra tickets.
    assert len(pf.list_tickets(sprint="all")) == 2


def test_explicit_v1_to_v2_migration_preserves_ticket_ids_and_lifecycle(tmp_path) -> None:
    from tests.test_delivery_plan import _candidate as _v1_cand
    from tests.test_delivery_plan import _plan as _v1_plan

    pf = Planfile(str(tmp_path))
    v1_plan = _v1_plan([_v1_cand("runtime-core", 0), _v1_cand("package-facade", 1, depends_on=["runtime-core"])])
    v1_state = pf.materialize_delivery_plan(v1_plan)
    orig_ids = {k: node["ticket_id"] for k, node in v1_state["candidates"].items()}

    v2_plan_hash = _digest({"migrated": v1_plan["plan_id"], "v": 2})
    v2_cands = [
        _v2_candidate("runtime-core", 0, home="semcod", plan_hash=v2_plan_hash),
        _v2_candidate(
            "package-facade",
            1,
            home="semcod",
            plan_hash=v2_plan_hash,
            depends_on=["runtime-core"],
        ),
    ]
    v2_plan = _v2_plan(
        plan_id=v1_plan["plan_id"],
        repository=v1_plan["repository"],
        home="semcod",
        base_sha=v1_plan["accepted_base_sha"],
        candidates=v2_cands,
        plan_hash=v2_plan_hash,
    )

    migrated = pf.migrate_delivery_plan_v1_to_v2(v2_plan)
    assert migrated["revision"] == 2
    assert migrated["placement"]["schema"] == DELIVERY_PLACEMENT_V2_SCHEMA
    assert {k: node["ticket_id"] for k, node in migrated["candidates"].items()} == orig_ids
    # Idempotent replay of migration does not bump revision or duplicate tickets.
    assert pf.migrate_delivery_plan_v1_to_v2(v2_plan) == migrated
    assert len(pf.list_tickets(sprint="all")) == 2

    # Checkpoints still work seamlessly on migrated v2 plans.
    ckpt = pf.checkpoint_delivery_candidate(
        {
            "schema": "planfile.delivery-checkpoint/v1",
            "checkpoint_ref": "checkpoint://semcod/planfile/runtime-core/v2-1",
            "plan_id": migrated["plan_id"],
            "plan_hash": migrated["plan_hash"],
            "candidate_key": "runtime-core",
            "candidate_digest": v2_cands[0]["candidate_digest"],
            "sequence": 1,
            "phase": "testing",
            "head_sha": "e" * 40,
            "evidence_refs": ["artifact://semcod/planfile/v2-report"],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    assert ckpt["candidates"]["runtime-core"]["status"] == "checkpointed"

    # Conflicting repository in migration fails closed before mutating.
    bad_repo_v2 = _v2_plan(
        plan_id=v1_plan["plan_id"],
        repository="uritime/autodo",
        home="uritime",
        base_sha=v1_plan["accepted_base_sha"],
        candidates=[
            _v2_candidate("runtime-core", 0, home="uritime", plan_hash=v2_plan_hash),
            _v2_candidate("package-facade", 1, home="uritime", plan_hash=v2_plan_hash, depends_on=["runtime-core"]),
        ],
        plan_hash=v2_plan_hash,
    )
    with pytest.raises(DeliveryPlanError, match="delivery_plan_migration_conflict"):
        pf.migrate_delivery_plan_v1_to_v2(bad_repo_v2)


def test_bundle_composition_matrix_12_vs_13_and_36_campaign_preflight(tmp_path, monkeypatch) -> None:
    from tests.test_delivery_plan import _candidate as _v1_cand
    from tests.test_delivery_plan import _plan as _v1_plan

    # 1. v1 preserves candidate_count <= 12 limit and rejects 13.
    v1_13 = _v1_plan([_v1_cand(f"item-{idx:02d}", idx) for idx in range(13)])
    with pytest.raises(ValidationError):
        CompiledWorkPlanV1.model_validate(v1_13)

    # 2. Bundle composition partitions 13 proposals deterministically into 12 + 1 with cross-chunk dependency.
    proposals_13 = [
        _proposal(
            f"item-{idx:02d}",
            repository="semcod/planfile",
            home="semcod",
            base_sha="a" * 40,
            depends_on=([f"item-{idx - 1:02d}"] if idx > 0 else []),
        )
        for idx in range(13)
    ]
    bundle_13 = compose_delivery_plan_bundle(
        proposals_13,
        bundle_id="split-13-matrix",
        bundle_ref="artifact://semcod/planfile/split-13",
    )
    assert [s.candidate_count for s in bundle_13.subplans] == [12, 1]
    assert bundle_13.subplans[1].candidates[0].external_depends_on[0].plan_id == bundle_13.subplans[0].plan_id

    # 3. Full 36-proposal campaign: AUTO10 + LLM10 + HEY10 + PLAN6.
    campaign_proposals: list[dict] = []
    # 6 PLAN proposals in semcod/planfile (PLAN-006 first, PLAN-001 depends on PLAN-006)
    for n in range(2, 7):
        campaign_proposals.append(
            _proposal(
                f"plan-{n:03d}",
                repository="semcod/planfile",
                home="semcod",
                base_sha="a" * 40,
            )
        )
    campaign_proposals.append(
        _proposal(
            "plan-001",
            repository="semcod/planfile",
            home="semcod",
            base_sha="a" * 40,
            depends_on=["plan-002", "plan-006"],
        )
    )
    for i in range(1, 11):
        deps = ["plan-001"] if i == 1 else [f"auto-{i - 1:03d}"]
        campaign_proposals.append(
            _proposal(
                f"auto-{i:03d}",
                repository="uritime/autodo",
                home="uritime",
                base_sha="b" * 40,
                depends_on=deps,
            )
        )
    for i in range(1, 11):
        campaign_proposals.append(
            _proposal(
                f"llm-{i:03d}",
                repository="subactor/subllm",
                home="subactor",
                base_sha="c" * 40,
                depends_on=(["plan-006"] if i == 1 else []),
            )
        )
    for i in range(1, 11):
        campaign_proposals.append(
            _proposal(
                f"hey-{i:03d}",
                repository="paxlet-com/heyasa",
                home="paxlet-com",
                base_sha="d" * 40,
                depends_on=(["plan-001", "auto-001"] if i == 1 else []),
            )
        )

    bundle = compose_delivery_plan_bundle(
        campaign_proposals,
        bundle_id="autodo-2026-11-18",
        bundle_ref="artifact://semcod/planfile/autodo-bundle-36",
    )
    bundle_dict = bundle.model_dump(mode="json", by_alias=True, exclude_none=False)
    assert bundle_dict["schema"] == DELIVERY_PLAN_BUNDLE_SCHEMA
    assert len(bundle.subplans) == 4
    counts_by_repo = {s.repository: s.candidate_count for s in bundle.subplans}
    assert counts_by_repo == {
        "uritime/autodo": 10,
        "subactor/subllm": 10,
        "paxlet-com/heyasa": 10,
        "semcod/planfile": 6,
    }

    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    resp = client.post("/delivery-plans/preflight", json=bundle_dict)
    assert resp.status_code == 200, resp.text
    pre = resp.json()
    assert pre["ok"] is True
    assert pre["kind"] == "delivery_plan_bundle"
    assert pre["subplan_count"] == 4
    assert sorted(pre["subplan_sizes"]) == [6, 10, 10, 10]
    assert pre["authority"] == "none"
    assert pre["execution"] == "inert"


def test_bundle_dry_run_replay_partial_resume_conflicts_and_execution_inert(tmp_path) -> None:
    proposals = [
        _proposal("plan-006", repository="semcod/planfile", home="semcod", base_sha="a" * 40),
        _proposal(
            "plan-001",
            repository="semcod/planfile",
            home="semcod",
            base_sha="a" * 40,
            depends_on=["plan-006"],
        ),
        _proposal(
            "auto-001",
            repository="uritime/autodo",
            home="uritime",
            base_sha="b" * 40,
            depends_on=["plan-001"],
        ),
        _proposal(
            "llm-001",
            repository="subactor/subllm",
            home="subactor",
            base_sha="c" * 40,
            depends_on=["plan-006"],
        ),
        _proposal(
            "hey-001",
            repository="paxlet-com/heyasa",
            home="paxlet-com",
            base_sha="d" * 40,
            depends_on=["auto-001", "llm-001"],
        ),
    ]
    bundle = compose_delivery_plan_bundle(
        proposals,
        bundle_id="campaign-mini",
        bundle_ref="artifact://semcod/planfile/campaign-mini",
    )
    bundle_dict = bundle.model_dump(mode="json", by_alias=True, exclude_none=False)
    pf = Planfile(str(tmp_path))

    # 1. Dry-run writes zero tickets and zero state files.
    dry = pf.materialize_delivery_bundle(bundle_dict, dry_run=True)
    assert dry["dry_run"] is True
    assert dry["candidate_count"] == 5
    assert pf.list_tickets(sprint="all") == []
    assert not (tmp_path / ".planfile" / "delivery-plans").exists()

    # 2. Partial materialization followed by crash recovery (missing bundle & subplan state).
    subplans_by_repo = {s["repository"]: s for s in bundle_dict["subplans"]}
    partial_1 = pf.materialize_delivery_plan(subplans_by_repo["semcod/planfile"])
    plan_001_id = partial_1["candidates"]["plan-001"]["ticket_id"]
    plan_006_id = partial_1["candidates"]["plan-006"]["ticket_id"]

    # Simulate state loss on disk for subplan before resuming full bundle.
    (tmp_path / ".planfile" / "delivery-plans" / f"{subplans_by_repo['semcod/planfile']['plan_id']}.json").unlink()
    full_state = pf.materialize_delivery_bundle(bundle_dict)
    assert len(full_state["ticket_ids"]) == 5
    assert (
        full_state["ticket_ids"][f"{subplans_by_repo['semcod/planfile']['plan_id']}:plan-001"]
        == plan_001_id
    )
    assert (
        full_state["ticket_ids"][f"{subplans_by_repo['semcod/planfile']['plan_id']}:plan-006"]
        == plan_006_id
    )

    # 3. Replay preserves exact same ticket IDs with zero duplicates.
    replay = pf.materialize_delivery_bundle(bundle_dict)
    assert replay["ticket_ids"] == full_state["ticket_ids"]
    assert len(pf.list_tickets(sprint="all")) == 5

    # 4. Cross-repo edges are real blocked_by / blocks on canonical tickets, and execution is inert!
    auto_tid = full_state["ticket_ids"][f"{subplans_by_repo['uritime/autodo']['plan_id']}:auto-001"]
    llm_tid = full_state["ticket_ids"][f"{subplans_by_repo['subactor/subllm']['plan_id']}:llm-001"]
    hey_tid = full_state["ticket_ids"][f"{subplans_by_repo['paxlet-com/heyasa']['plan_id']}:hey-001"]
    auto_ticket = pf.get_ticket(auto_tid)
    hey_ticket = pf.get_ticket(hey_tid)
    assert auto_ticket is not None and auto_ticket.blocked_by == [plan_001_id]
    assert hey_ticket is not None and set(hey_ticket.blocked_by) == {auto_tid, llm_tid}
    assert hey_tid in (pf.get_ticket(auto_tid).blocks or [])
    assert hey_tid in (pf.get_ticket(llm_tid).blocks or [])
    for ticket in pf.list_tickets(sprint="all"):
        assert ticket.executor is None
        assert ticket.source is not None
        assert ticket.source.context["authority"] == "none"
        assert ticket.source.context["execution"] == "inert"

    # 5. Conflicts on bundle_hash / accepted_base_sha / unknown cross-plan dependency fail closed.
    tampered_bundle = dict(bundle_dict, bundle_hash="sha256:" + "f" * 64)
    with pytest.raises(ValidationError, match="delivery_plan_bundle_hash_mismatch"):
        DeliveryPlanBundleV1.model_validate(tampered_bundle)

    # Unknown external dependency outside bundle / unobserved target.
    with pytest.raises(ValueError, match="delivery_plan_bundle_dependency_unknown"):
        compose_delivery_plan_bundle(
            [_proposal("orphan", repository="semcod/planfile", home="semcod", base_sha="a" * 40, depends_on=["missing-dep"])],
            bundle_id="bad-deps",
            bundle_ref="artifact://semcod/planfile/bad-deps",
        )

    # Conflicting base SHA for same repository inside a bundle fails before writes.
    with pytest.raises(ValueError, match="delivery_plan_bundle_repository_conflict"):
        compose_delivery_plan_bundle(
            [
                _proposal("a-1", repository="uritime/autodo", home="uritime", base_sha="1" * 40),
                _proposal("a-2", repository="uritime/autodo", home="uritime", base_sha="2" * 40),
            ],
            bundle_id="bad-base",
            bundle_ref="artifact://uritime/autodo/bad-base",
        )

    # Standalone subplan referencing an unmaterialized external plan fails closed before ticket write.
    dangling = _v2_plan(
        plan_id="dangling-sub",
        repository="uritime/autodo",
        home="uritime",
        base_sha="b" * 40,
        candidates=[
            _v2_candidate(
                "auto-dangling",
                0,
                home="uritime",
                external_depends_on=[{"plan_id": "nonexistent-plan", "candidate_key": "missing"}],
            )
        ],
    )
    pf2 = Planfile(str(tmp_path / "isolated"))
    with pytest.raises(DeliveryPlanError, match="delivery_plan_external_dependency_unresolved"):
        pf2.materialize_delivery_plan(dangling)
    assert pf2.list_tickets(sprint="all") == []


def test_bundle_crash_between_bulk_create_and_blocker_wiring_repairs_inverse_blocks(
    tmp_path, monkeypatch
):
    from planfile.delivery_plan import DeliveryPlanRepository

    proposals = [
        _proposal("plan-001", repository="semcod/planfile", home="semcod", base_sha="a" * 40),
        _proposal(
            "auto-001",
            repository="uritime/autodo",
            home="uritime",
            base_sha="b" * 40,
            depends_on=["plan-001"],
        ),
    ]
    bundle = compose_delivery_plan_bundle(
        proposals,
        bundle_id="crash-wiring",
        bundle_ref="artifact://semcod/planfile/crash-wiring",
    )
    bundle_dict = bundle.model_dump(mode="json", by_alias=True, exclude_none=False)
    pf = Planfile(str(tmp_path))
    subplans_by_repo = {s["repository"]: s for s in bundle_dict["subplans"]}

    original_wire = DeliveryPlanRepository._wire_blocker_blocks_unlocked

    def fail_once(self, edges):
        raise RuntimeError("simulated_crash_before_wiring")

    monkeypatch.setattr(DeliveryPlanRepository, "_wire_blocker_blocks_unlocked", fail_once)
    with pytest.raises(RuntimeError, match="simulated_crash_before_wiring"):
        pf.materialize_delivery_bundle(bundle_dict)

    # First subplan finished, second bulk-created auto-001 before wiring blocker's blocks list.
    assert len(pf.list_tickets(sprint="all")) == 2
    by_key = {
        t.source.context["candidate_key"]: t
        for t in pf.list_tickets(sprint="all")
        if t.source and isinstance(t.source.context, dict)
    }
    blocker = by_key["plan-001"]
    dependent = by_key["auto-001"]
    assert dependent.blocked_by == [blocker.id]
    assert blocker.blocks == []

    monkeypatch.setattr(DeliveryPlanRepository, "_wire_blocker_blocks_unlocked", original_wire)
    recovered = pf.materialize_delivery_bundle(bundle_dict)
    assert recovered["ticket_ids"][f"{subplans_by_repo['semcod/planfile']['plan_id']}:plan-001"] == blocker.id
    assert recovered["ticket_ids"][f"{subplans_by_repo['uritime/autodo']['plan_id']}:auto-001"] == dependent.id
    assert len(pf.list_tickets(sprint="all")) == 2

    reloaded_blocker = pf.get_ticket(blocker.id)
    assert reloaded_blocker is not None
    assert dependent.id in (reloaded_blocker.blocks or [])

