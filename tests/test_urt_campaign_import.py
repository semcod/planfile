"""Unit tests for URT campaign metadata mapping and deduplicated Planfile import (CQRS-028)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from planfile.sync.receipts import publish_intent, record_receipt
from planfile.sync.urt_campaign_import import (
    CAMPAIGN_METADATA_SCHEMA,
    DEDUP_KEY_V2_PREFIX,
    MAPPED_TICKET_SCHEMA,
    UrtCampaignImportError,
    UrtCampaignRevisionConflictError,
    assert_not_raw_backlog_payload,
    build_urt_dedup_key,
    commit_urt_campaign_import,
    map_urt_campaign_item_to_planfile,
    prepare_urt_campaign_preview,
)


def _sample_item(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "campaign_id": "uritime-cqrs-es-20261118",
        "proposal_id": "CQRS-028",
        "native_ticket_id": "PLF-027",
        "title": "Map URT metadata into Planfile",
        "priority": "P1",
        "plan_revision": 1,
        "tracking_repository": "semcod/planfile",
        "target_repository_candidate": "Nieustalone; wymaga routowania",
        "original_phrase": "codziennie o 08:30 Europe/Warsaw przed synchronizacją",
        "urt_ref": "urt:v1:instant:2026-11-19T07:30:00Z",
        "temporal_intent": {
            "kind": "recurring",
            "timezone": "Europe/Warsaw",
            "anchor": "before:sync",
        },
        "resolution_metadata": {
            "tzdb_version": "2026f",
            "interpreter_confidence": "verified_ast",
        },
        "evidences": ["uritime/src/uritime/planfile_sync.py", "autodo/tools/planfile_import.py"],
        "proposal_disposition": "planned_backlog_item",
        "accepted": False,
    }
    base.update(overrides)
    return base


def test_ac01_rejects_raw_backlog_manifest_without_mapping() -> None:
    with pytest.raises(UrtCampaignImportError, match="without mapping"):
        assert_not_raw_backlog_payload({"campaign_manifest": "BACKLOG.json", "proposals": [{"id": "CQRS-028"}]})

    with pytest.raises(UrtCampaignImportError, match="without mapping"):
        assert_not_raw_backlog_payload(_sample_item())

    mapped = map_urt_campaign_item_to_planfile(_sample_item())
    assert mapped["schema"] == MAPPED_TICKET_SCHEMA
    assert_not_raw_backlog_payload(mapped)


@pytest.mark.parametrize("payload", [
    {"schema": "uritime.evolution-plan/v1", "campaign": "uritime-cqrs-es-20261118", "tickets": []},
    {"native_planfile_payload": False, "tickets": []},
    {
        "id": "CQRS-001", "title": "Define event records", "ticket_path": "tickets/CQRS-001.md",
        "target_projects": ["uritime"], "target_repository_candidate": None,
    },
])
def test_rejects_evolution_plan_manifest_and_unmapped_items(payload) -> None:
    with pytest.raises(UrtCampaignImportError, match="without mapping"):
        assert_not_raw_backlog_payload(payload)


def test_native_ticket_can_share_fields_with_an_evolution_proposal() -> None:
    assert_not_raw_backlog_payload({"id": "CQRS-001", "name": "Track an approved change"})
    assert_not_raw_backlog_payload({"ticket_path": "tickets/native.md", "target_projects": ["uritime"]})


def test_ac02_deduplicates_identical_import_and_guards_revisions(tmp_path: Path) -> None:
    state_path = tmp_path / "import_state.json"
    receipt_path = tmp_path / "import_receipt.json"
    manifest = {"items": [_sample_item()]}

    p1 = prepare_urt_campaign_preview(manifest, state_path=state_path)
    assert len(p1["operations"]) == 1
    assert p1["operations"][0]["action"] == "create"
    r1 = commit_urt_campaign_import(p1, state_path=state_path, receipt_output_path=receipt_path)
    assert r1["results"] == [
        {"dedup_key": "uritime-cqrs-es-20261118:CQRS-028", "action": "create", "plan_revision": 1}
    ]

    p2 = prepare_urt_campaign_preview(manifest, state_path=state_path)
    assert p2["operations"][0]["action"] == "noop_duplicate"
    assert p2["operations"][0]["duplicate"] is True
    r2 = commit_urt_campaign_import(p2, state_path=state_path, receipt_output_path=receipt_path)
    assert r2["results"][0]["action"] == "noop_duplicate"

    before_state = state_path.read_text(encoding="utf-8")
    before_receipt = receipt_path.read_text(encoding="utf-8")
    changed_same_rev = {"items": [_sample_item(title="Modified without rev bump", plan_revision=1)]}
    with pytest.raises(UrtCampaignRevisionConflictError, match="plan_revision > 1"):
        prepare_urt_campaign_preview(changed_same_rev, state_path=state_path)
    assert state_path.read_text(encoding="utf-8") == before_state
    assert receipt_path.read_text(encoding="utf-8") == before_receipt

    bumped = {"items": [_sample_item(title="Clarified title in revision 2", plan_revision=2)]}
    p3 = prepare_urt_campaign_preview(bumped, state_path=state_path)
    assert p3["operations"][0]["action"] == "supersede_revision"
    assert p3["operations"][0]["supersedes_revision"] == 1
    r3 = commit_urt_campaign_import(p3, state_path=state_path, receipt_output_path=receipt_path)
    assert r3["results"][0]["action"] == "supersede_revision"


def test_ac03_separates_tracking_from_unrouted_target() -> None:
    unrouted = map_urt_campaign_item_to_planfile(_sample_item(target_repository_candidate="Nieustalone"))
    assert unrouted["routing"]["tracking_repository"] == "semcod/planfile"
    assert unrouted["routing"]["target_repository_candidate"] is None
    assert unrouted["routing"]["routing_status"] == "unrouted"

    routed = map_urt_campaign_item_to_planfile(_sample_item(target_repository_candidate="uritime/autodo"))
    assert routed["routing"]["tracking_repository"] == "semcod/planfile"
    assert routed["routing"]["target_repository_candidate"] == "uritime/autodo"
    assert routed["routing"]["routing_status"] == "candidate_declared"


def test_ac04_preserves_original_intent_and_unaccepted_status() -> None:
    mapped = map_urt_campaign_item_to_planfile(_sample_item())
    meta = mapped["native_ticket"]["inputs"]["urt_campaign"]
    assert meta["schema"] == CAMPAIGN_METADATA_SCHEMA
    assert meta["original_phrase"] == "codziennie o 08:30 Europe/Warsaw przed synchronizacją"
    assert meta["urt_ref"] == "urt:v1:instant:2026-11-19T07:30:00Z"
    assert meta["temporal_intent"]["kind"] == "recurring"
    assert meta["resolution_metadata"]["tzdb_version"] == "2026f"
    assert meta["proposal_disposition"] == "planned_backlog_item"
    assert meta["proposal_accepted"] is False
    assert mapped["native_ticket"]["status"] == "open"


def test_ac05_binds_github_issue_only_from_verified_sync_receipt(tmp_path: Path) -> None:
    planfile_dir = tmp_path / ".planfile"
    # Unverified hint in item is ignored when no succeeded readback receipt exists.
    hinted_only = map_urt_campaign_item_to_planfile(
        _sample_item(github_issue=9999), planfile_dir=planfile_dir
    )
    assert hinted_only["github_binding"]["linked_issue"] is None
    assert hinted_only["github_binding"]["unverified_hint_ignored"] is True

    intent = publish_intent(
        "PLF-027",
        {"name": "[CQRS-028] Map URT metadata", "status": "open", "priority": "high"},
        "github",
        "semcod/planfile",
    )
    receipt, _ = record_receipt(
        planfile_dir,
        intent,
        operation="create",
        outcome="succeeded",
        remote_id="431",
        remote_url="https://github.com/semcod/planfile/issues/431",
        remote_key="#431",
    )

    verified = map_urt_campaign_item_to_planfile(_sample_item(github_issue=9999), planfile_dir=planfile_dir)
    assert verified["github_binding"]["linked_issue"] == 431
    assert verified["github_binding"]["receipt_id"] == receipt["receipt_id"]
    assert verified["github_binding"]["unverified_hint_ignored"] is False


def test_distinct_identifier_pairs_with_colons_never_collide(tmp_path: Path) -> None:
    assert build_urt_dedup_key("uritime-cqrs-es-20261118", "CQRS-028") == "uritime-cqrs-es-20261118:CQRS-028"
    k1 = build_urt_dedup_key("a:b", "c")
    k2 = build_urt_dedup_key("a", "b:c")
    k3 = build_urt_dedup_key("urt-key/v2", '["a:b","c"]')
    assert len({k1, k2, k3}) == 3
    assert all(k.startswith(DEDUP_KEY_V2_PREFIX) for k in (k1, k2, k3))

    state_path = tmp_path / "import_state.json"
    receipt_path = tmp_path / "import_receipt.json"
    manifest = {
        "items": [
            _sample_item(campaign_id="a:b", proposal_id="c", title="First pair"),
            _sample_item(campaign_id="a", proposal_id="b:c", title="Second pair"),
            _sample_item(campaign_id="urt-key/v2", proposal_id='["a:b","c"]', title="Adversarial pair"),
        ]
    }
    preview = prepare_urt_campaign_preview(manifest, state_path=state_path)
    assert [op["action"] for op in preview["operations"]] == ["create", "create", "create"]
    assert len({op["dedup_key"] for op in preview["operations"]}) == 3

    receipt = commit_urt_campaign_import(preview, state_path=state_path, receipt_output_path=receipt_path)
    assert len(receipt["results"]) == 3
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(saved["entries"].keys()) == {k1, k2, k3}


def test_stale_noop_duplicate_preview_rejected_after_newer_revision_commit(tmp_path: Path) -> None:
    state_path = tmp_path / "import_state.json"
    receipt_path = tmp_path / "import_receipt.json"
    rev1 = {"items": [_sample_item(title="v1", plan_revision=1)]}
    p1 = prepare_urt_campaign_preview(rev1, state_path=state_path)
    commit_urt_campaign_import(p1, state_path=state_path, receipt_output_path=receipt_path)

    stale_noop = prepare_urt_campaign_preview(rev1, state_path=state_path)
    assert stale_noop["operations"][0]["action"] == "noop_duplicate"
    assert stale_noop["operations"][0]["plan_revision"] == 1

    rev2 = {"items": [_sample_item(title="v2", plan_revision=2)]}
    p2 = prepare_urt_campaign_preview(rev2, state_path=state_path)
    assert p2["operations"][0]["action"] == "supersede_revision"
    commit_urt_campaign_import(p2, state_path=state_path, receipt_output_path=receipt_path)

    before_state = state_path.read_text(encoding="utf-8")
    stale_receipt_path = tmp_path / "stale_receipt.json"
    with pytest.raises(UrtCampaignRevisionConflictError, match="Stale noop_duplicate"):
        commit_urt_campaign_import(
            stale_noop, state_path=state_path, receipt_output_path=stale_receipt_path
        )
    assert not stale_receipt_path.exists()
    assert state_path.read_text(encoding="utf-8") == before_state

    # Even if rev 3 reverts title back to v1, committing rev-1 stale_noop must still fail (rev 3 != 1).
    rev3 = {"items": [_sample_item(title="v1", plan_revision=3)]}
    p3 = prepare_urt_campaign_preview(rev3, state_path=state_path)
    commit_urt_campaign_import(p3, state_path=state_path, receipt_output_path=receipt_path)
    with pytest.raises(UrtCampaignRevisionConflictError, match="Stale noop_duplicate"):
        commit_urt_campaign_import(
            stale_noop, state_path=state_path, receipt_output_path=stale_receipt_path
        )
    assert not stale_receipt_path.exists()

    # Stale supersede preview prepared before a competing revision landed is also rejected.
    stale_sup_receipt = tmp_path / "stale_sup_receipt.json"
    state_at_rev1 = tmp_path / "rev1_state.json"
    commit_urt_campaign_import(
        prepare_urt_campaign_preview(rev1, state_path=state_at_rev1),
        state_path=state_at_rev1,
        receipt_output_path=tmp_path / "rev1_receipt.json",
    )
    stale_supersede = prepare_urt_campaign_preview(
        {"items": [_sample_item(title="competing v4", plan_revision=4)]},
        state_path=state_at_rev1,
    )
    with pytest.raises(UrtCampaignRevisionConflictError, match="Stale supersede revision"):
        commit_urt_campaign_import(
            stale_supersede, state_path=state_path, receipt_output_path=stale_sup_receipt
        )
    assert not stale_sup_receipt.exists()

    # Missing persisted state also rejects a noop_duplicate preview fail-closed.
    missing_state_path = tmp_path / "missing_state.json"
    with pytest.raises(UrtCampaignRevisionConflictError, match="Stale noop_duplicate"):
        commit_urt_campaign_import(
            stale_noop, state_path=missing_state_path, receipt_output_path=stale_receipt_path
        )
    assert not stale_receipt_path.exists()


def test_reads_pre_change_persisted_state_and_preserves_plain_receipt_bindings(tmp_path: Path) -> None:
    state_path = tmp_path / "import_state.json"
    receipt_path = tmp_path / "import_receipt.json"
    planfile_dir = tmp_path / ".planfile"

    plain_mapped = map_urt_campaign_item_to_planfile(_sample_item())
    colon_mapped = map_urt_campaign_item_to_planfile(
        _sample_item(campaign_id="org:camp", proposal_id="PROP-1")
    )
    legacy_colon_key = "org:camp:PROP-1"
    pre_change_state = {
        "entries": {
            plain_mapped["dedup_key"]: {
                "dedup_key": plain_mapped["dedup_key"],
                "plan_revision": 1,
                "content_digest": plain_mapped["content_digest"],
                "native_ticket": plain_mapped["native_ticket"],
                "routing": plain_mapped["routing"],
                "github_binding": plain_mapped["github_binding"],
                "revision_history": [{"plan_revision": 1, "content_digest": plain_mapped["content_digest"]}],
            },
            legacy_colon_key: {
                "dedup_key": legacy_colon_key,
                "plan_revision": 1,
                "content_digest": colon_mapped["content_digest"],
                "native_ticket": colon_mapped["native_ticket"],
                "routing": colon_mapped["routing"],
                "github_binding": colon_mapped["github_binding"],
                "revision_history": [{"plan_revision": 1, "content_digest": colon_mapped["content_digest"]}],
            },
        }
    }
    state_path.write_text(json.dumps(pre_change_state, indent=2), encoding="utf-8")

    # Identical re-import of legacy colon entry matches by embedded identity -> noop_duplicate.
    # Different split ("org", "camp:PROP-1") must NOT match the legacy entry -> create!
    preview_mixed = prepare_urt_campaign_preview(
        {
            "items": [
                _sample_item(campaign_id="org:camp", proposal_id="PROP-1"),
                _sample_item(campaign_id="org", proposal_id="camp:PROP-1"),
            ]
        },
        state_path=state_path,
    )
    assert [op["action"] for op in preview_mixed["operations"]] == ["noop_duplicate", "create"]
    commit_urt_campaign_import(preview_mixed, state_path=state_path, receipt_output_path=receipt_path)

    # Superseding pre-change colon entry preserves history and migrates key to canonical v2 key.
    preview_sup = prepare_urt_campaign_preview(
        {"items": [_sample_item(campaign_id="org:camp", proposal_id="PROP-1", title="Updated", plan_revision=2)]},
        state_path=state_path,
    )
    assert preview_sup["operations"][0]["action"] == "supersede_revision"
    assert preview_sup["operations"][0]["supersedes_revision"] == 1
    commit_urt_campaign_import(preview_sup, state_path=state_path, receipt_output_path=receipt_path)

    saved = json.loads(state_path.read_text(encoding="utf-8"))["entries"]
    canonical_colon_key = build_urt_dedup_key("org:camp", "PROP-1")
    assert legacy_colon_key not in saved
    assert canonical_colon_key in saved
    assert len(saved[canonical_colon_key]["revision_history"]) == 2
    assert plain_mapped["dedup_key"] in saved

    # Plain-key receipt binding remains intact.
    intent = publish_intent(
        "uritime-cqrs-es-20261118:CQRS-028",
        {"name": "[CQRS-028] Plain receipt", "status": "open", "priority": "high"},
        "github",
        "semcod/planfile",
    )
    rcp, _ = record_receipt(
        planfile_dir,
        intent,
        operation="create",
        outcome="succeeded",
        remote_id="478",
        remote_url="https://github.com/semcod/planfile/issues/478",
        remote_key="#478",
    )
    verified = map_urt_campaign_item_to_planfile(
        _sample_item(native_ticket_id=None), planfile_dir=planfile_dir
    )
    assert verified["github_binding"]["linked_issue"] == 478
    assert verified["github_binding"]["receipt_id"] == rcp["receipt_id"]
