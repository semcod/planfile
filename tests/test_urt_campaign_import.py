"""Unit tests for URT campaign metadata mapping and deduplicated Planfile import (CQRS-028)."""
from __future__ import annotations

from pathlib import Path

import pytest

from planfile.sync.receipts import publish_intent, record_receipt
from planfile.sync.urt_campaign_import import (
    CAMPAIGN_METADATA_SCHEMA,
    MAPPED_TICKET_SCHEMA,
    UrtCampaignImportError,
    UrtCampaignRevisionConflictError,
    assert_not_raw_backlog_payload,
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
