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


@pytest.mark.parametrize(
    ("field", "limit"),
    [("description", 4096), ("body", 4096), ("name", 512), ("title", 512), ("labels", 128)],
)
def test_publication_identity_includes_content_beyond_preview_limit(field, limit):
    ticket = _ticket()
    if field == "body":
        ticket.pop("description")
    if field == "title":
        ticket.pop("name")
    value = "x" * limit
    ticket[field] = [value + "old"] if field == "labels" else value + "old"
    before = publish_intent("PLF-1", ticket, "github", "owner/repo")
    ticket[field] = [value + "new"] if field == "labels" else value + "new"
    after = publish_intent("PLF-1", ticket, "github", "owner/repo")

    assert before["payload"] == after["payload"]  # previews remain bounded
    assert before["payload_digest"] != after["payload_digest"]
    assert before["idempotency_key"] != after["idempotency_key"]


def test_long_body_with_legacy_receipt_updates_once_without_recreating_issue(tmp_path):
    store = _store(tmp_path)
    ticket = _ticket()
    ticket["description"] = "x" * 4096 + "new deployment result"
    ticket["sync"] = {"github": {"id": "42", "repository": "owner/repo"}}
    # Older writers computed identity from just this prefix.
    legacy = publish_intent(
        "PLF-1", {**ticket, "description": ticket["description"][:4096]},
        "github", "owner/repo",
    )
    record_receipt(store.base_dir, legacy, operation="update", outcome="succeeded", remote_id="42")

    class RecordingBackend(Backend):
        def update_ticket(self, external_id, **fields):
            super().update_ticket(external_id, **fields)
            assert fields["body"] == ticket["description"]

    backend = RecordingBackend()
    first = sync_to_external(backend, [("PLF-1", ticket)], False, store, "github")
    second = sync_to_external(backend, [("PLF-1", ticket)], False, store, "github")

    assert first.updated == ("PLF-1",)
    assert second.reused == ("PLF-1",)
    assert backend.updated == ["42"]
    assert backend.created == []
    receipts = (store.base_dir / "sync/github.receipts.jsonl").read_text()
    assert len(receipts.splitlines()) == 2
    assert "new deployment result" not in receipts  # no raw body in durable receipts


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


def test_later_failure_and_recovery_preserve_history_and_remote_identity(tmp_path):
    intent = publish_intent("PLF-2", _ticket(), "github", "owner/repo")
    directory = tmp_path / ".planfile"
    def record(outcome, remote_id="7", error_type=None):
        return record_receipt(directory, intent, operation="update", outcome=outcome,
                              remote_id=remote_id, error_type=error_type)
    success, created = record("succeeded")
    assert created
    failure, created = record("failed", error_type="RuntimeError")
    assert created and failure["attempt"] == 2
    assert record("failed", error_type="RuntimeError") == (failure, False)
    recovered, created = record("succeeded")
    assert created and recovered["attempt"] == 3
    assert record("succeeded") == (recovered, False)
    assert successful_receipt(directory, "github", intent["idempotency_key"]) == recovered
    with pytest.raises(SyncReceiptConflict):
        record("succeeded", remote_id="8")
    assert success["remote_id"] == recovered["remote_id"] == "7"
