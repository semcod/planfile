from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from planfile import Planfile
from planfile.api import server
from planfile.cli.commands import app
from planfile.core.fastio import mirror_path


def _disable_archive(pf: Planfile) -> None:
    config = pf.store._read_config()
    config["archive"]["enabled"] = False
    pf.store._write_config(config)


def _create_tickets(pf: Planfile, count: int, *, sprint: str = "current") -> list[str]:
    return [
        pf.create_ticket(name=f"Ticket {number}", sprint=sprint).id
        for number in range(1, count + 1)
    ]


def test_migration_partitions_tickets_and_preserves_contract(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ids = _create_tickets(pf, 205)
    before = {
        ticket.id: ticket.model_dump(mode="json", exclude_none=True)
        for ticket in pf.list_tickets(sprint="all")
    }

    report = pf.store.migrate_to_sharded_yaml(shard_size=100)

    assert report["backend"] == "sharded-yaml"
    assert report["tickets"] == 205
    assert Path(report["backup_dir"]).is_dir()
    assert not (tmp_path / ".planfile" / "sprints" / "current.yaml").exists()
    shard_dir = tmp_path / ".planfile" / "sprints" / "current.shards"
    assert [path.name for path in sorted(shard_dir.glob("tickets-*.yaml"))] == [
        "tickets-000000-000099.yaml",
        "tickets-000100-000199.yaml",
        "tickets-000200-000299.yaml",
    ]
    manifest = json.loads((shard_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "planfile.sharded-yaml/v1"
    assert manifest["ticket_count"] == 205

    after = {
        ticket.id: ticket.model_dump(mode="json", exclude_none=True)
        for ticket in pf.list_tickets(sprint="all")
    }
    assert after == before
    assert pf.get_ticket(ids[-1]).name == "Ticket 205"


def test_sharded_crud_move_and_sprint_save(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    first, second = _create_tickets(pf, 2)
    pf.store.migrate_to_sharded_yaml(shard_size=1)

    updated = pf.update_ticket(first, priority="high")
    assert updated is not None and updated.priority == "high"

    assert pf.store.move_ticket(second, "release-1") is True
    moved = pf.get_ticket(second)
    assert moved is not None and moved.sprint == "release-1"
    assert [ticket.id for ticket in pf.list_tickets(sprint="release-1")] == [second]

    stale = pf.store.load_sprint("current")
    created = pf.create_ticket(name="Created after snapshot")
    pf.store.save_sprint("current", stale)
    assert pf.get_ticket(created.id) is not None

    assert pf.delete_ticket(first) is True
    assert pf.get_ticket(first) is None


def test_update_rewrites_only_one_ticket_shard(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ids = _create_tickets(pf, 250)
    legacy_size = (tmp_path / ".planfile" / "sprints" / "current.yaml").stat().st_size
    pf.store.migrate_to_sharded_yaml(shard_size=100)

    writes: list[Path] = []
    original = pf.store._write_yaml_atomic

    def counted(path, data, *, allow_unicode=False):
        writes.append(Path(path))
        return original(path, data, allow_unicode=allow_unicode)

    monkeypatch.setattr(pf.store, "_write_yaml_atomic", counted)
    updated = pf.update_ticket(ids[-1], priority="critical")

    ticket_shard_writes = [
        path for path in writes
        if path.name.startswith("tickets-") and path.suffix == ".yaml"
    ]
    assert updated is not None and updated.priority == "critical"
    assert len(ticket_shard_writes) == 1
    assert ticket_shard_writes[0].stat().st_size < legacy_size / 2


def test_custom_ids_use_stable_hash_shards(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    pf.store.migrate_to_sharded_yaml(shard_size=100, custom_shards=8)
    storage = pf.store._sharded_storage()

    assert storage.shard_name("CUSTOM-alpha") == storage.shard_name("CUSTOM-alpha")
    assert storage.shard_name("CUSTOM-alpha").startswith("tickets-custom-")


def test_sharded_archiving_keeps_active_tickets(tmp_path):
    pf = Planfile(str(tmp_path))
    config = pf.store._read_config()
    config["archive"].update(
        max_current_tickets=3,
        max_current_bytes=0,
        retain_terminal_tickets=1,
    )
    pf.store._write_config(config)
    pf.store.migrate_to_sharded_yaml(shard_size=2)

    first = pf.create_ticket(name="old done")
    pf.update_ticket(first.id, status="done")
    second = pf.create_ticket(name="new done")
    pf.update_ticket(second.id, status="done")
    active_a = pf.create_ticket(name="active a")
    active_b = pf.create_ticket(name="active b")

    assert pf.get_ticket(first.id).sprint.startswith("archive-")
    assert pf.get_ticket(second.id).sprint == "current"
    assert {ticket.id for ticket in pf.list_tickets(sprint="current")} == {
        second.id,
        active_a.id,
        active_b.id,
    }


def test_sharded_api_lists_and_creates_sprints(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    _create_tickets(pf, 3)
    pf.store.migrate_to_sharded_yaml(shard_size=2)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)

    listed = client.get("/tickets", params={"sprint": "current", "view": "summary"})
    sprints = client.get("/sprints")
    created = client.post(
        "/sprints",
        json={"id": "release-1", "name": "Release 1"},
    )

    assert listed.status_code == 200 and len(listed.json()) == 3
    assert sprints.status_code == 200
    assert next(item for item in sprints.json() if item["id"] == "current")[
        "ticket_count"
    ] == 3
    assert created.status_code == 201
    assert (tmp_path / ".planfile" / "sprints" / "release-1.shards").is_dir()


def test_external_shard_edit_invalidates_model_cache(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    ticket_id = _create_tickets(pf, 1)[0]
    pf.store.migrate_to_sharded_yaml(shard_size=100)
    assert pf.get_ticket(ticket_id).name == "Ticket 1"
    assert pf.list_tickets(sprint="current")[0].name == "Ticket 1"

    shard = pf.store._sharded_storage().shard_path("current", ticket_id)
    data = yaml.safe_load(shard.read_text(encoding="utf-8"))
    data["tickets"][ticket_id]["name"] = "Edited externally"
    shard.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    mirror_path(shard).unlink(missing_ok=True)

    assert pf.list_tickets(sprint="current")[0].name == "Edited externally"


def test_migration_refuses_nonempty_target(tmp_path):
    pf = Planfile(str(tmp_path))
    target = tmp_path / ".planfile" / "sprints" / "current.shards"
    target.mkdir()
    (target / "unexpected").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(ValueError, match="sharded_target_not_empty"):
        pf.store.migrate_to_sharded_yaml()

    assert (tmp_path / ".planfile" / "sprints" / "current.yaml").exists()


def test_storage_cli_reports_and_migrates(tmp_path):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    _create_tickets(pf, 3)
    runner = CliRunner()

    before = runner.invoke(
        app,
        ["storage", "status", "--project", str(tmp_path), "--json"],
    )
    migrated = runner.invoke(
        app,
        [
            "storage",
            "migrate",
            "--project",
            str(tmp_path),
            "--shard-size",
            "2",
            "--yes",
            "--json",
        ],
    )
    after = runner.invoke(
        app,
        ["storage", "status", "--project", str(tmp_path), "--json"],
    )

    assert before.exit_code == 0
    assert json.loads(before.output)["backend"] == "single-yaml"
    assert migrated.exit_code == 0
    assert json.loads(migrated.output)["tickets"] == 3
    assert after.exit_code == 0
    assert json.loads(after.output)["backend"] == "sharded-yaml"


@pytest.mark.parametrize("sharded", [False, True])
def test_bulk_create_writes_each_affected_ticket_file_once(tmp_path, monkeypatch, sharded):
    pf = Planfile(str(tmp_path))
    _disable_archive(pf)
    if sharded:
        pf.store.migrate_to_sharded_yaml(shard_size=100)
    writes: list[Path] = []
    original = pf.store._write_yaml_atomic

    def counted(path, data, *, allow_unicode=False):
        writes.append(Path(path))
        return original(path, data, allow_unicode=allow_unicode)

    monkeypatch.setattr(pf.store, "_write_yaml_atomic", counted)
    created = pf.create_tickets_bulk(
        [{"name": f"Bulk {number}"} for number in range(50)]
    )
    ticket_writes = [
        path
        for path in writes
        if path.name == "current.yaml" or path.name.startswith("tickets-")
    ]

    assert len(created) == 50
    assert len(ticket_writes) == 1
    assert len(pf.list_tickets(sprint="current")) == 50


def test_bulk_create_rejects_over_limit_instead_of_silently_truncating(tmp_path):
    pf = Planfile(str(tmp_path))

    with pytest.raises(ValueError, match="bulk_ticket_limit_exceeded"):
        pf.create_tickets_bulk([{"name": str(number)} for number in range(51)])

    assert pf.list_tickets(sprint="current") == []
