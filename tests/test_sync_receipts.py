from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from planfile.core.store import Store
from planfile.sync.outbound import OutboundSyncError, sync_to_external
from planfile.sync.receipts import (
    SyncReceiptConflict,
    publish_intent,
    record_receipt,
    successful_receipt,
)


class Backend:
    config = {"repo": "owner/repo"}

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.created: list[str] = []
        self.updated: list[str] = []

    def create_ticket(self, payload):
        self.created.append(payload["metadata"]["planfile_id"])
        if self.fail:
            raise RuntimeError("provider unavailable; secret value is redacted")
        return SimpleNamespace(
            id="42",
            url="https://github.com/owner/repo/issues/42",
            key="owner/repo#42",
        )

    def update_ticket(self, external_id, **fields):
        self.updated.append(str(external_id))


def _store(tmp_path):
    store = Store(tmp_path)
    store.init()
    return store


def _ticket(name: str = "publish me") -> dict:
    return {
        "id": "PLF-1",
        "name": name,
        "description": "safe body",
        "status": "open",
        "labels": ["planfile"],
        "integration": ["github"],
    }


def test_successful_retry_is_deduplicated_by_payload_digest(tmp_path):
    store = _store(tmp_path)
    ticket = _ticket()
    first = Backend()

    result = sync_to_external(first, [(ticket["id"], ticket)], False, store, "github")
    assert result.succeeded == ("PLF-1",)
    assert first.created and first.created[0].endswith(":PLF-1")

    second = Backend()
    repeated = sync_to_external(second, [(ticket["id"], ticket)], False, store, "github")
    assert repeated.succeeded == ("PLF-1",)
    assert second.created == []
    assert second.updated == []

    lines = (tmp_path / ".planfile" / "sync" / "github.receipts.jsonl").read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["outcome"] == "succeeded"


def test_changed_payload_gets_a_new_receipt_and_updates_existing_issue(tmp_path):
    store = _store(tmp_path)
    ticket = _ticket()
    first = Backend()
    sync_to_external(first, [(ticket["id"], ticket)], False, store, "github")

    ticket["description"] = "changed body"
    second = Backend()
    sync_to_external(second, [(ticket["id"], ticket)], False, store, "github")

    assert second.created == []
    assert second.updated == ["42"]
    lines = (tmp_path / ".planfile" / "sync" / "github.receipts.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_failed_attempt_is_recorded_without_raw_error_and_can_retry(tmp_path):
    store = _store(tmp_path)
    ticket = _ticket()
    with pytest.raises(OutboundSyncError):
        sync_to_external(Backend(fail=True), [(ticket["id"], ticket)], False, store, "github")

    receipt_file = tmp_path / ".planfile" / "sync" / "github.receipts.jsonl"
    first = json.loads(receipt_file.read_text().splitlines()[0])
    assert first["outcome"] == "failed"
    assert "secret value is redacted" not in receipt_file.read_text()

    retry = Backend()
    result = sync_to_external(retry, [(ticket["id"], ticket)], False, store, "github")
    assert result.succeeded == ("PLF-1",)
    assert len(receipt_file.read_text().splitlines()) == 2


def test_receipt_conflict_and_url_redaction_are_fail_closed(tmp_path):
    intent = publish_intent("PLF-2", _ticket("conflict"), "github", "owner/repo")
    first, recorded = record_receipt(
        tmp_path / ".planfile",
        intent,
        operation="create",
        outcome="succeeded",
        remote_id="7",
        remote_url="https://github.com/owner/repo/issues/7?redacted=1",
    )
    assert recorded is True
    assert first["remote_url"] == "https://github.com/owner/repo/issues/7"
    assert successful_receipt(tmp_path / ".planfile", "github", intent["idempotency_key"]) == first

    with pytest.raises(SyncReceiptConflict):
        record_receipt(
            tmp_path / ".planfile",
            intent,
            operation="create",
            outcome="succeeded",
            remote_id="8",
        )
