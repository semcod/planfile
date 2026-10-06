from __future__ import annotations

import json

import yaml

from planfile import Planfile


def test_allocator_does_not_reuse_deleted_ticket_id_from_journal(tmp_path):
    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["next_id"] = 1
    pf.store._write_config(config)

    operations = tmp_path / ".planfile" / "events" / "operations.jsonl"
    operations.parent.mkdir(parents=True, exist_ok=True)
    operations.write_text(
        json.dumps({"event": {"ticket_id": "PLF-066", "kind": "task"}}) + "\n",
        encoding="utf-8",
    )

    created = pf.create_ticket(name="Keep historical IDs reserved")

    assert created.id == "PLF-067"
    assert pf.store._read_config()["next_id"] == 68


def test_allocator_does_not_reuse_published_id_from_sync_state(tmp_path):
    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["next_id"] = 1
    pf.store._write_config(config)

    sync_file = tmp_path / ".planfile" / "sync" / "github.state.yaml"
    sync_file.parent.mkdir(parents=True, exist_ok=True)
    sync_file.write_text(
        yaml.safe_dump(
            {
                "schema": "planfile.sync-state/v2",
                "backend": "github",
                "repository": "semcod/planfile",
                "ticket_map": {"PLF-066": "86"},
            }
        ),
        encoding="utf-8",
    )

    created = pf.create_ticket(name="Prevent collision with published issue")

    assert created.id == "PLF-067"
    assert pf.store._read_config()["next_id"] == 68


def test_allocator_does_not_reuse_published_marker_from_sync_receipts(tmp_path):
    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["next_id"] = 1
    pf.store._write_config(config)

    receipts_file = tmp_path / ".planfile" / "sync" / "github.receipts.jsonl"
    receipts_file.parent.mkdir(parents=True, exist_ok=True)
    receipts_file.write_text(
        json.dumps(
            {
                "operation": "create",
                "outcome": "succeeded",
                "remote_id": "86",
                "ticket_id": "PLF-066",
                "intent": {
                    "deduplication_key": "PLF-066",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    created = pf.create_ticket(name="Prevent collision with published receipt")

    assert created.id == "PLF-067"
    assert pf.store._read_config()["next_id"] == 68


def test_allocator_does_not_reuse_deduplication_marker_in_ticket_description(tmp_path):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(
        name="Existing marker carrier",
        description="<!-- planfile:deduplication-key=PLF-066 -->\nSome description",
    )
    # Reset config next_id back to 1 to simulate a fresh branch or stale config
    config = pf.store._read_config()
    config["next_id"] = 1
    pf.store._write_config(config)

    created = pf.create_ticket(name="Allocated after marker")

    assert created.id == "PLF-067"
    assert pf.store._read_config()["next_id"] == 68
