"""Regression tests for ticket create --dry-run, --sync-dry-run warnings, and unsynced notices."""

import hashlib
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from planfile import Planfile
from planfile.cli.groups.ticket import register_ticket_commands


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_dir():
            digest.update(f"D:{rel}\n".encode())
        elif path.is_file():
            digest.update(f"F:{rel}\n".encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture()
def ticket_cli():
    app = typer.Typer()
    register_ticket_commands(app)
    return app


def test_ticket_create_dry_run_leaves_initialized_store_hash_and_next_id_unchanged(
    ticket_cli, tmp_path, monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    pf.store.init()
    pf.create_ticket("Seed ticket", dedupe_key="seed")
    (pf.store.base_dir / "github.planfile.yaml").write_text(
        "integrations:\n  github:\n    repo: owner/repo\n",
        encoding="utf-8",
    )

    before_next_id = int(pf.store._read_config()["next_id"])
    assert before_next_id == 2
    before_hash = _tree_hash(pf.store.base_dir)

    runner = CliRunner()
    with patch("planfile.cli.groups.ticket.commands._inbound_sync_before_create") as inbound, \
         patch("planfile.cli.groups.ticket.commands._auto_sync") as outbound:
        result = runner.invoke(
            ticket_cli,
            ["ticket", "create", "dry run probe", "--dry-run", "--no-inbound-sync"],
        )
        assert result.exit_code == 0, result.output
        assert "--dry-run" in result.output
        assert "PLF-002" in result.output

        # Also test dedupe preview without mutating anything.
        dedupe_res = runner.invoke(
            ticket_cli,
            ["ticket", "create", "dup probe", "--dedupe-key", "seed", "--dry-run"],
        )
        assert dedupe_res.exit_code == 0, dedupe_res.output
        assert "Would reuse PLF-001" in dedupe_res.output

    inbound.assert_not_called()
    outbound.assert_not_called()
    assert int(pf.store._read_config()["next_id"]) == before_next_id
    assert _tree_hash(pf.store.base_dir) == before_hash
    assert [t.id for t in pf.list_tickets(sprint="all")] == ["PLF-001"]


def test_ticket_create_dry_run_in_uninitialized_git_repo_creates_no_planfile_dir(
    ticket_cli, tmp_path, monkeypatch,
):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(ticket_cli, ["ticket", "create", "dry run probe", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "--dry-run" in result.output
    assert "PLF-001" in result.output
    assert not (tmp_path / ".planfile").exists()


def test_ticket_create_sync_dry_run_warns_that_local_ticket_was_written(
    ticket_cli, tmp_path, monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    pf.store.init()
    (pf.store.base_dir / "github.planfile.yaml").write_text(
        "integrations:\n  github:\n    repo: owner/repo\n",
        encoding="utf-8",
    )

    with patch("planfile.cli.groups.ticket.commands._auto_sync") as outbound:
        result = CliRunner().invoke(
            ticket_cli,
            ["ticket", "create", "Sync preview", "--sync-dry-run", "--no-inbound-sync"],
        )
    assert result.exit_code == 0, result.output
    assert "--sync-dry-run previews remote sync only; local ticket was written" in result.output
    assert "--dry-run" in result.output
    assert pf.get_ticket("PLF-001") is not None
    assert outbound.called


def test_ticket_update_warns_for_synced_ticket_unless_no_sync_or_sync(
    ticket_cli, tmp_path, monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    pf.store.init()
    pf.create_ticket("Synced ticket", integration=["github"])
    pf.create_ticket("Local ticket")

    runner = CliRunner()
    with patch("planfile.cli.groups.ticket.commands._auto_sync") as outbound:
        default_res = runner.invoke(ticket_cli, ["ticket", "update", "PLF-001", "--status", "in_progress"])
        assert default_res.exit_code == 0, default_res.output
        assert "not synced to remote (github)" in default_res.output
        assert "--sync" in default_res.output
        outbound.assert_not_called()

        quiet_res = runner.invoke(ticket_cli, ["ticket", "update", "PLF-001", "--priority", "high", "--no-sync"])
        assert quiet_res.exit_code == 0, quiet_res.output
        assert "not synced to remote" not in quiet_res.output
        outbound.assert_not_called()

        local_res = runner.invoke(ticket_cli, ["ticket", "update", "PLF-002", "--status", "in_progress"])
        assert local_res.exit_code == 0, local_res.output
        assert "not synced to remote" not in local_res.output
        outbound.assert_not_called()

        synced_res = runner.invoke(ticket_cli, ["ticket", "update", "PLF-001", "--priority", "critical", "--sync"])
        assert synced_res.exit_code == 0, synced_res.output
        assert "not synced to remote" not in synced_res.output
        outbound.assert_called_once()


def test_ticket_delete_and_bulk_update_warn_for_synced_tickets_unless_no_sync(
    ticket_cli, tmp_path, monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    pf.store.init()
    pf.create_ticket("Remote one", integration=["github"])
    pf.create_ticket("Remote two", sync={"github": {"id": "42"}})

    runner = CliRunner()
    with patch("planfile.cli.groups.ticket.commands._auto_sync") as outbound:
        bulk_default = runner.invoke(
            ticket_cli,
            ["ticket", "bulk-update", "--new-status", "in_progress", "--force"],
        )
        assert bulk_default.exit_code == 0, bulk_default.output
        assert "not synced to remote (github): PLF-001, PLF-002" in bulk_default.output

        bulk_quiet = runner.invoke(
            ticket_cli,
            ["ticket", "bulk-update", "--new-priority", "high", "--force", "--no-sync"],
        )
        assert bulk_quiet.exit_code == 0, bulk_quiet.output
        assert "not synced to remote" not in bulk_quiet.output

        del_default = runner.invoke(ticket_cli, ["ticket", "delete", "PLF-001", "--force"])
        assert del_default.exit_code == 0, del_default.output
        assert "not synced to remote (github): PLF-001" in del_default.output

        del_quiet = runner.invoke(ticket_cli, ["ticket", "delete", "PLF-002", "--force", "--no-sync"])
        assert del_quiet.exit_code == 0, del_quiet.output
        assert "not synced to remote" not in del_quiet.output
        outbound.assert_not_called()
