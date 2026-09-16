from __future__ import annotations

from types import SimpleNamespace

import pytest

from planfile.core.store import Store
from planfile.sync import operations
from planfile.sync.outbound import OutboundSyncError


class PartialBackend:
    config = {"repo": "owner/repo"}

    def __init__(self):
        self.created: list[str] = []

    def create_ticket(self, payload):
        local_id = payload["metadata"]["planfile_id"]
        self.created.append(local_id)
        if local_id.endswith(":bad"):
            raise RuntimeError("controlled provider failure")
        return SimpleNamespace(
            id=local_id,
            url=f"https://github.com/owner/repo/issues/{local_id}",
            key=f"owner/repo#{local_id}",
        )


class LostResponseBackend:
    config = {"repo": "owner/repo"}

    def __init__(self, matches):
        self.matches = matches
        self.create_calls = 0
        self.search_calls: list[str] = []

    def create_ticket(self, payload):
        self.create_calls += 1
        raise RuntimeError("connection lost after provider commit")

    def search_tickets(self, query):
        self.search_calls.append(query)
        return self.matches


class ReadbackBackend(PartialBackend):
    def __init__(self, title: str = "PLF-1"):
        super().__init__()
        self.readbacks = 0
        self.title = title

    def create_ticket(self, payload):
        local_id = payload["metadata"]["planfile_id"]
        self.created.append(local_id)
        return SimpleNamespace(
            id="42",
            url="https://github.com/owner/repo/issues/42",
            key="owner/repo#42",
        )

    def get_ticket(self, remote_id):
        self.readbacks += 1
        return SimpleNamespace(
            id=str(remote_id),
            name=self.title,
            url="https://github.com/owner/repo/issues/42",
            key="owner/repo#42",
        )


def _store(tmp_path):
    store = Store(tmp_path)
    store.init()
    return store


def _ticket(ticket_id: str) -> dict:
    return {
        "id": ticket_id,
        "name": ticket_id,
        "description": "safe body",
        "status": "open",
        "integration": ["github"],
    }


def test_legacy_operations_uses_fail_closed_batch_result(tmp_path):
    store = _store(tmp_path)
    backend = PartialBackend()

    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(
            backend,
            [("good", _ticket("good")), ("bad", _ticket("bad"))],
            False,
            store,
            "github",
        )

    result = caught.value.result
    assert result.succeeded == ("good",)
    assert result.created == ("good",)
    assert result.failed == ("bad",)
    assert result.to_dict() == {
        "created": ["good"],
        "reused": [],
        "updated": [],
        "failed": ["bad"],
        "planned": [],
        "succeeded": ["good"],
    }


def test_lost_create_response_recovers_one_marker_without_retrying_create(tmp_path):
    store = _store(tmp_path)
    ticket = _ticket("PLF-1")
    remote = SimpleNamespace(
        id="42",
        url="https://github.com/owner/repo/issues/42",
        key="owner/repo#42",
    )
    backend = LostResponseBackend([remote])

    result = operations.sync_to_external(
        backend,
        [("PLF-1", ticket)],
        False,
        store,
        "github",
    )

    assert result.reused == ("PLF-1",)
    assert result.created == ()
    assert backend.create_calls == 1
    assert backend.search_calls == ["PLF-1"]
    assert ticket["sync"]["github"]["id"] == "42"
    receipt = tmp_path / ".planfile" / "sync" / "github.receipts.jsonl"
    assert '"outcome": "succeeded"' in receipt.read_text()


def test_ambiguous_lost_create_is_failed_and_never_retried(tmp_path):
    store = _store(tmp_path)
    backend = LostResponseBackend(
        [
            {"id": "41", "url": "https://github.com/owner/repo/issues/41"},
            {"id": "42", "url": "https://github.com/owner/repo/issues/42"},
        ]
    )

    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(
            backend,
            [("PLF-1", _ticket("PLF-1"))],
            False,
            store,
            "github",
        )

    assert caught.value.result.failed == ("PLF-1",)
    assert backend.create_calls == 1
    assert backend.search_calls == ["PLF-1"]


def test_successful_create_requires_matching_provider_readback_when_available(tmp_path):
    store = _store(tmp_path)
    backend = ReadbackBackend()

    result = operations.sync_to_external(
        backend,
        [("PLF-1", _ticket("PLF-1"))],
        False,
        store,
        "github",
    )

    assert result.created == ("PLF-1",)
    assert backend.readbacks == 1


def test_readback_mismatch_is_failed_closed(tmp_path):
    store = _store(tmp_path)
    backend = ReadbackBackend(title="unexpected remote title")

    with pytest.raises(OutboundSyncError) as caught:
        operations.sync_to_external(
            backend,
            [("PLF-1", _ticket("PLF-1"))],
            False,
            store,
            "github",
        )

    assert caught.value.result.failed == ("PLF-1",)
    assert len(backend.created) == 1
