from __future__ import annotations

import json

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
