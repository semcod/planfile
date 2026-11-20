"""Map URT campaign manifests to Planfile contracts with revision-safe deduplication (CQRS-028)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from planfile.sync.receipts import latest_ticket_receipts

MAPPED_TICKET_SCHEMA = "planfile.urt-mapped-ticket/v1"
CAMPAIGN_METADATA_SCHEMA = "planfile.urt-campaign-metadata/v1"
PREVIEW_SCHEMA = "planfile.urt-campaign-preview/v1"
IMPORT_RECEIPT_SCHEMA = "planfile.urt-campaign-import-receipt/v1"

_PRIORITY_MAP: dict[str, str] = {
    "P0": "critical",
    "P1": "high",
    "P2": "medium",
    "P3": "low",
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}
_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


class UrtCampaignImportError(ValueError):
    """Fail-closed validation or routing error while preparing a URT campaign import."""


class UrtCampaignRevisionConflictError(UrtCampaignImportError):
    """Raised when changed content under an existing dedup_key lacks a higher plan_revision."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-urt-", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _clean_nonempty(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UrtCampaignImportError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_target_candidate(raw_target: object) -> tuple[str | None, str]:
    if raw_target is None:
        return None, "unrouted"
    text = str(raw_target).strip()
    lowered = text.lower()
    if not text or any(tok in lowered for tok in ("unrouted", "unknown", "nieustalone", "unverified", "tbd")):
        return None, "unrouted"
    if not _REPO_SLUG_RE.fullmatch(text):
        raise UrtCampaignImportError(f"Invalid target_repository_candidate: {text!r}")
    return text, "candidate_declared"


def _resolve_verified_issue_binding(
    *,
    dedup_key: str,
    native_ticket_id: str | None,
    tracking_repository: str,
    planfile_dir: Path | None,
    verified_receipts: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[int | None, str | None, str | None]:
    receipts_map: dict[str, Mapping[str, Any]] = {}
    if planfile_dir is not None:
        receipts_map.update(latest_ticket_receipts(planfile_dir, "github", tracking_repository))
    if verified_receipts:
        receipts_map.update(verified_receipts)

    for candidate_key in (k for k in (native_ticket_id, dedup_key) if k):
        rcp = receipts_map.get(candidate_key)
        if not isinstance(rcp, Mapping):
            continue
        if rcp.get("outcome") != "succeeded":
            continue
        remote_raw = str(rcp.get("remote_id") or "").strip()
        if remote_raw.isdigit():
            remote_num = int(remote_raw)
            if remote_num >= 1:
                return remote_num, str(rcp.get("receipt_id") or "") or None, rcp.get("remote_url")  # type: ignore[arg-type]
    return None, None, None


def assert_not_raw_backlog_payload(payload: Mapping[str, Any]) -> None:
    """Reject passing unmapped BACKLOG.json or raw campaign manifests directly as native payloads."""
    if not isinstance(payload, Mapping):
        raise UrtCampaignImportError("Native Planfile ticket payload must be a mapping")
    if (
        payload.get("schema") == "uritime.evolution-plan/v1"
        or payload.get("native_planfile_payload") is False
    ):
        raise UrtCampaignImportError("Raw URT evolution plan cannot be submitted without mapping")
    proposal_fields = {"id", "title", "ticket_path", "target_projects"}
    if proposal_fields.issubset(payload):
        raise UrtCampaignImportError("Raw URT backlog item cannot be submitted without mapping")
    if payload.get("schema") == MAPPED_TICKET_SCHEMA:
        return
    raw_markers = {"proposals", "campaign_manifest", "backlog_version", "proposal_id"}
    present = raw_markers & set(payload.keys())
    if present:
        raise UrtCampaignImportError(
            f"Raw BACKLOG.json/campaign payload cannot be submitted directly without mapping: {sorted(present)}"
        )


def map_urt_campaign_item_to_planfile(
    item: Mapping[str, Any],
    *,
    planfile_dir: Path | None = None,
    verified_receipts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Map one URT campaign proposal item into a validated Planfile contract payload."""
    if not isinstance(item, Mapping):
        raise UrtCampaignImportError("Campaign item must be a mapping")

    campaign_id = _clean_nonempty(item.get("campaign_id"), "campaign_id")
    proposal_id = _clean_nonempty(item.get("proposal_id"), "proposal_id")
    title = _clean_nonempty(item.get("title"), "title")
    tracking_repo = _clean_nonempty(item.get("tracking_repository"), "tracking_repository")
    if not _REPO_SLUG_RE.fullmatch(tracking_repo):
        raise UrtCampaignImportError(f"Invalid tracking_repository: {tracking_repo!r}")

    plan_rev = item.get("plan_revision")
    if isinstance(plan_rev, bool) or not isinstance(plan_rev, int) or plan_rev < 1:
        raise UrtCampaignImportError("plan_revision must be an integer >= 1")

    raw_priority = str(item.get("priority") or "P1").strip()
    if raw_priority not in _PRIORITY_MAP:
        raise UrtCampaignImportError(f"Unsupported priority: {raw_priority!r}")
    mapped_priority = _PRIORITY_MAP[raw_priority]

    target_candidate, routing_status = _normalize_target_candidate(item.get("target_repository_candidate"))

    original_phrase = _clean_nonempty(item.get("original_phrase"), "original_phrase")
    urt_ref = _clean_nonempty(item.get("urt_ref"), "urt_ref")
    if not urt_ref.startswith("urt:"):
        raise UrtCampaignImportError(f"urt_ref must preserve canonical urt: prefix, got {urt_ref!r}")

    temporal_intent = item.get("temporal_intent")
    if not isinstance(temporal_intent, Mapping) or not temporal_intent:
        raise UrtCampaignImportError("temporal_intent must be a non-empty structured mapping")
    resolution_meta = item.get("resolution_metadata")
    if resolution_meta is not None and not isinstance(resolution_meta, Mapping):
        raise UrtCampaignImportError("resolution_metadata must be a mapping when provided")

    evidences_raw = item.get("evidences") or ()
    if isinstance(evidences_raw, (str, bytes)) or not isinstance(evidences_raw, Sequence):
        raise UrtCampaignImportError("evidences must be a sequence")
    evidences = [str(ev) for ev in evidences_raw]

    native_id_raw = item.get("native_ticket_id")
    native_ticket_id = str(native_id_raw).strip() if isinstance(native_id_raw, str) and native_id_raw.strip() else None
    dedup_key = f"{campaign_id}:{proposal_id}"

    linked_issue, linked_receipt_id, linked_url = _resolve_verified_issue_binding(
        dedup_key=dedup_key,
        native_ticket_id=native_ticket_id,
        tracking_repository=tracking_repo,
        planfile_dir=planfile_dir,
        verified_receipts=verified_receipts,
    )
    unverified_hint_present = item.get("github_issue") is not None or item.get("issue_number") is not None

    disposition = str(item.get("proposal_disposition") or "planned_backlog_item").strip()
    accepted = bool(item.get("accepted") is True and disposition == "accepted")

    semantic_body = {
        "campaign_id": campaign_id,
        "proposal_id": proposal_id,
        "title": title,
        "priority": mapped_priority,
        "tracking_repository": tracking_repo,
        "target_repository_candidate": target_candidate,
        "routing_status": routing_status,
        "original_phrase": original_phrase,
        "urt_ref": urt_ref,
        "temporal_intent": dict(temporal_intent),
        "resolution_metadata": dict(resolution_meta or {}),
        "evidences": evidences,
        "proposal_disposition": disposition,
        "accepted": accepted,
    }
    content_digest = _sha256_json(semantic_body)

    metadata_attachment = {
        "schema": CAMPAIGN_METADATA_SCHEMA,
        "campaign_id": campaign_id,
        "proposal_id": proposal_id,
        "native_ticket_id": native_ticket_id,
        "dedup_key": dedup_key,
        "plan_revision": plan_rev,
        "content_digest": content_digest,
        "tracking_repository": tracking_repo,
        "target_repository_candidate": target_candidate,
        "routing_status": routing_status,
        "original_phrase": original_phrase,
        "urt_ref": urt_ref,
        "temporal_intent": dict(temporal_intent),
        "resolution_metadata": dict(resolution_meta or {}),
        "evidences": evidences,
        "proposal_disposition": disposition,
        "proposal_accepted": accepted,
        "linked_github_issue": linked_issue,
        "linked_receipt_id": linked_receipt_id,
        "linked_github_url": linked_url,
        "unverified_issue_hint_ignored": bool(unverified_hint_present and linked_issue is None),
    }

    return {
        "schema": MAPPED_TICKET_SCHEMA,
        "dedup_key": dedup_key,
        "content_digest": content_digest,
        "plan_revision": plan_rev,
        "native_ticket": {
            "name": f"[{proposal_id}] {title}",
            "priority": mapped_priority,
            "status": "open",
            "inputs": {
                "urt_campaign": metadata_attachment,
            },
        },
        "routing": {
            "tracking_repository": tracking_repo,
            "target_repository_candidate": target_candidate,
            "routing_status": routing_status,
        },
        "github_binding": {
            "linked_issue": linked_issue,
            "receipt_id": linked_receipt_id,
            "url": linked_url,
            "unverified_hint_ignored": metadata_attachment["unverified_issue_hint_ignored"],
        },
    }


def _load_import_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"entries": {}}
    loaded = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not isinstance(loaded.get("entries"), dict):
        raise UrtCampaignImportError(f"Malformed campaign import state: {state_path}")
    return loaded


def prepare_urt_campaign_preview(
    manifest: Mapping[str, Any],
    *,
    state_path: Path,
    planfile_dir: Path | None = None,
    verified_receipts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic deduplicated preview and reject conflicting same-revision mutations."""
    if not isinstance(manifest, Mapping):
        raise UrtCampaignImportError("Manifest must be a mapping")
    items = manifest.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise UrtCampaignImportError("Manifest 'items' must be a sequence")

    state = _load_import_state(state_path)
    existing_entries: dict[str, Any] = state["entries"]
    operations: list[dict[str, Any]] = []
    seen_in_batch: dict[str, str] = {}

    for raw_item in items:
        mapped = map_urt_campaign_item_to_planfile(
            raw_item, planfile_dir=planfile_dir, verified_receipts=verified_receipts
        )
        dkey = mapped["dedup_key"]
        cdig = mapped["content_digest"]
        prev_rev_item = seen_in_batch.get(dkey)
        if prev_rev_item is not None:
            if prev_rev_item == cdig:
                continue
            raise UrtCampaignRevisionConflictError(
                f"Conflicting duplicate items for {dkey!r} inside single manifest batch"
            )
        seen_in_batch[dkey] = cdig

        prior = existing_entries.get(dkey)
        if prior is None:
            operations.append({
                "action": "create",
                "duplicate": False,
                "dedup_key": dkey,
                "plan_revision": mapped["plan_revision"],
                "content_digest": cdig,
                "supersedes_revision": None,
                "mapped_ticket": mapped,
            })
        elif prior.get("content_digest") == cdig:
            operations.append({
                "action": "noop_duplicate",
                "duplicate": True,
                "dedup_key": dkey,
                "plan_revision": int(prior["plan_revision"]),
                "content_digest": cdig,
                "supersedes_revision": None,
                "mapped_ticket": mapped,
            })
        elif mapped["plan_revision"] <= int(prior.get("plan_revision", 0)):
            raise UrtCampaignRevisionConflictError(
                f"Changed content for {dkey!r} requires plan_revision > {prior.get('plan_revision')} "
                f"(got {mapped['plan_revision']})"
            )
        else:
            operations.append({
                "action": "supersede_revision",
                "duplicate": False,
                "dedup_key": dkey,
                "plan_revision": mapped["plan_revision"],
                "content_digest": cdig,
                "supersedes_revision": int(prior["plan_revision"]),
                "mapped_ticket": mapped,
            })

    return {
        "schema": PREVIEW_SCHEMA,
        "preview_digest": _sha256_json([
            {
                "action": op["action"],
                "dedup_key": op["dedup_key"],
                "plan_revision": op["plan_revision"],
                "content_digest": op["content_digest"],
            }
            for op in operations
        ]),
        "operations": operations,
    }


def commit_urt_campaign_import(
    preview: Mapping[str, Any],
    *,
    state_path: Path,
    receipt_output_path: Path,
) -> dict[str, Any]:
    """Persist mapped campaign state and emit a deduplication receipt without losing history."""
    if not isinstance(preview, Mapping) or preview.get("schema") != PREVIEW_SCHEMA:
        raise UrtCampaignImportError("Invalid campaign import preview payload")
    ops = preview.get("operations")
    if not isinstance(ops, Sequence):
        raise UrtCampaignImportError("Preview operations missing")

    state = _load_import_state(state_path)
    entries: dict[str, Any] = dict(state["entries"])

    applied: list[dict[str, Any]] = []
    for op in ops:
        action = str(op.get("action") or "")
        dkey = str(op.get("dedup_key") or "")
        cdig = str(op.get("content_digest") or "")
        rev = int(op.get("plan_revision") or 0)
        mapped = op["mapped_ticket"]
        prior = entries.get(dkey)

        if action == "noop_duplicate":
            applied.append({"dedup_key": dkey, "action": "noop_duplicate", "plan_revision": rev})
            continue
        if action == "create":
            if prior is not None:
                if prior.get("content_digest") == cdig:
                    applied.append({"dedup_key": dkey, "action": "noop_duplicate", "plan_revision": int(prior["plan_revision"])})
                    continue
                raise UrtCampaignRevisionConflictError(f"Concurrent entry created for {dkey!r}")
            entries[dkey] = {
                "dedup_key": dkey,
                "plan_revision": rev,
                "content_digest": cdig,
                "native_ticket": mapped["native_ticket"],
                "routing": mapped["routing"],
                "github_binding": mapped["github_binding"],
                "revision_history": [{"plan_revision": rev, "content_digest": cdig}],
            }
            applied.append({"dedup_key": dkey, "action": "create", "plan_revision": rev})
        elif action == "supersede_revision":
            if prior is None or rev <= int(prior.get("plan_revision", 0)):
                raise UrtCampaignRevisionConflictError(f"Stale supersede revision for {dkey!r}")
            history = list(prior.get("revision_history") or [])
            history.append({"plan_revision": rev, "content_digest": cdig})
            entries[dkey] = {
                "dedup_key": dkey,
                "plan_revision": rev,
                "content_digest": cdig,
                "supersedes_revision": int(prior["plan_revision"]),
                "native_ticket": mapped["native_ticket"],
                "routing": mapped["routing"],
                "github_binding": mapped["github_binding"],
                "revision_history": history,
            }
            applied.append({
                "dedup_key": dkey,
                "action": "supersede_revision",
                "plan_revision": rev,
                "supersedes_revision": int(prior["plan_revision"]),
            })
        else:
            raise UrtCampaignImportError(f"Unsupported preview action: {action!r}")

    _atomic_write_json(state_path, {"entries": entries})
    receipt = {
        "schema": IMPORT_RECEIPT_SCHEMA,
        "preview_digest": preview.get("preview_digest"),
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "results": applied,
    }
    _atomic_write_json(receipt_output_path, receipt)
    return receipt
