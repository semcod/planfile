"""Regression tests for repository-bound operational ticket intake and sync store mode (#304)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import yaml
from starlette.testclient import TestClient

from planfile import Planfile
from planfile.api import server as api_server
from planfile.core.store import PlanfileStore
from planfile.project_paths import (
    OPERATIONAL_RECEIPT_FILENAME,
    canonical_project_root,
    is_operational_store_enabled,
    resolve_operational_base_dir,
)
from planfile.sync.outbound import sync_to_external
from planfile.sync.state import SyncState


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _init_tracked_planfile_repo(tmp_path: Path, repo_name: str = "semcod/monag") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "remote", "add", "origin", f"https://github.com/{repo_name}.git")

    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def run() -> int:\n    return 0\n", encoding="utf-8")

    pf_dir = repo / ".planfile"
    (pf_dir / "sprints").mkdir(parents=True)
    (pf_dir / "sync").mkdir(parents=True)
    (pf_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "project": "monag",
                "prefix": "PLF",
                "next_id": 34,
                "archive": PlanfileStore.DEFAULT_ARCHIVE_CONFIG,
                "storage": PlanfileStore.DEFAULT_STORAGE_CONFIG,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (pf_dir / "github.planfile.yaml").write_text(
        yaml.safe_dump({"integrations": {"github": {"repo": repo_name}}}, sort_keys=False),
        encoding="utf-8",
    )
    (pf_dir / "sprints" / "current.yaml").write_text(
        yaml.safe_dump(
            {
                "sprint": {
                    "id": "sprint-001",
                    "name": "Sprint 1",
                    "status": "active",
                    "tickets": {
                        "PLF-033": {
                            "id": "PLF-033",
                            "name": "Existing tracked ticket",
                            "status": "open",
                            "priority": "normal",
                            "integration": ["github"],
                            "created_at": "2026-10-27T00:00:00+00:00",
                            "updated_at": "2026-10-27T00:00:00+00:00",
                        }
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (pf_dir / "sprints" / "backlog.yaml").write_text(
        yaml.safe_dump(
            {"sprint": {"id": "backlog", "name": "Backlog", "status": "active", "tickets": {}}},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (pf_dir / "sync" / "github.state.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "planfile.sync-state/v2",
                "backend": "github",
                "repository": repo_name,
                "repository_id": "R_12345",
                "ticket_map": {"PLF-033": "154"},
                "synced_at": "2026-10-27T00:00:00+00:00",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Initial tracked planfile baseline")
    return repo


class _FakeGitHubBackend:
    def __init__(self, repo: str = "semcod/monag"):
        self.config = {"repo": repo}
        self.created: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self.updated: list[tuple[str, dict]] = []

    @staticmethod
    def resolve_repository_identity(backend, candidate: str | None = None) -> dict:
        target = candidate or backend.config.get("repo") or "semcod/monag"
        return {"repository": target, "repository_id": "R_12345"}

    def get_ticket(self, external_id: str):
        return self.by_id.get(str(external_id))

    def find_ticket_by_deduplication_key(self, key: str):
        return None

    def create_ticket(self, ticket_data: dict) -> dict:
        self.created.append(ticket_data)
        issue_id = str(154 + len(self.created))
        record = {
            "id": issue_id,
            "name": ticket_data.get("name"),
            "description": ticket_data.get("description"),
            "status": ticket_data.get("status", "open"),
            "url": f"https://github.com/semcod/monag/issues/{issue_id}",
        }
        self.by_id[issue_id] = record
        return record

    def update_ticket(self, external_id: str, ticket_data: dict) -> bool:
        self.updated.append((external_id, ticket_data))
        return True


def _clean_primary_admission_check(repo: Path) -> tuple[bool, list[str]]:
    """Simulate clean-primary governance admission check (git status --porcelain)."""
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    dirty_lines = [line for line in status.splitlines() if line.strip()]
    return len(dirty_lines) == 0, dirty_lines


def test_operational_intake_and_sync_keep_tracked_primary_clean(tmp_path: Path) -> None:
    """AC-01 & AC-02: Creating and syncing a ticket in operational mode keeps primary clean; dirty source refuses."""
    repo = _init_tracked_planfile_repo(tmp_path)

    store = PlanfileStore(repo)
    receipt = store.enable_operational_intake(persist_git_config=True)
    assert receipt["enabled"] is True
    assert receipt["status"] == "ready"
    assert is_operational_store_enabled(repo) is True

    pf = Planfile(str(repo))
    assert pf.store.operational_mode is True
    assert pf.store.base_dir == resolve_operational_base_dir(repo)

    ticket, created = pf.create_ticket_deduplicated(
        "Classify historical Planfile diagnostics in Monag resume",
        description="Operational intake ticket for Monag#155",
        integration=["github"],
        dedupe_key="semcod/monag:plf-034",
    )
    assert created is True
    assert ticket.id == "PLF-034"

    backend = _FakeGitHubBackend("semcod/monag")
    current = pf.store.load_sprint("current")
    sprint_tickets = current.get("sprint", current).get("tickets", {})
    tickets = [(tid, tdata) for tid, tdata in sprint_tickets.items() if tid == "PLF-034"]
    sync_to_external(backend, tickets, False, pf.store, "github", None, None)

    sync_state = SyncState(pf.store.base_dir, "github")
    assert sync_state.get_remote_id("PLF-034") == "155"
    expected_identity = hashlib.sha256(str((repo / ".planfile").resolve()).encode("utf-8")).hexdigest()[:16]
    assert sync_state.store_identity == expected_identity

    clean, dirty = _clean_primary_admission_check(repo)
    assert clean is True, f"Expected clean primary checkout after operational create+sync, got {dirty}"

    # AC-02: A real dirty source file in the primary checkout still refuses clean-primary admission
    (repo / "src" / "app.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    clean_after_source_edit, dirty_after_source_edit = _clean_primary_admission_check(repo)
    assert clean_after_source_edit is False
    assert any("src/app.py" in line for line in dirty_after_source_edit)


def test_interrupted_migration_recovery_and_rollback_preserve_ids_and_mappings(tmp_path: Path) -> None:
    """AC-03: Interrupted migration recovery and rollback preserve ticket IDs, mappings, and tracked state."""
    repo = _init_tracked_planfile_repo(tmp_path)
    op_dir = resolve_operational_base_dir(repo)
    op_dir.mkdir(parents=True, exist_ok=True)

    # Simulate an interrupted migration with a staging marker and partial stale next_id
    (op_dir / ".migration-staging").write_text('{"started_at": "2026-10-28T00:00:00Z"}\n', encoding="utf-8")
    (op_dir / "config.yaml").write_text(
        yaml.safe_dump({"project": "monag", "prefix": "PLF", "next_id": 2}, sort_keys=False),
        encoding="utf-8",
    )
    (op_dir / OPERATIONAL_RECEIPT_FILENAME).write_text(
        json.dumps({"schema": "planfile.operational-store/v1", "enabled": True, "status": "migrating"}),
        encoding="utf-8",
    )

    pf = Planfile(str(repo))
    assert pf.store.operational_mode is True
    receipt = json.loads((op_dir / OPERATIONAL_RECEIPT_FILENAME).read_text(encoding="utf-8"))
    assert receipt["status"] == "ready"
    assert receipt["recovered_interrupted"] is True
    assert not (op_dir / ".migration-staging").exists()

    # Existing tracked ticket PLF-033 and mapping -> #154 are preserved
    existing = pf.get_ticket("PLF-033")
    assert existing is not None
    assert existing.name == "Existing tracked ticket"
    sync_state = SyncState(pf.store.base_dir, "github")
    assert sync_state.get_remote_id("PLF-033") == "154"

    # Allocator high-water respects PLF-033 / next_id=34 and allocates PLF-034
    allocated = pf.create_ticket("Post-recovery ticket")
    assert allocated.id == "PLF-034"

    # Rollback disables operational mode without touching tracked files when restore_tracked_files=False
    rb_receipt = pf.store.rollback_operational_intake(restore_tracked_files=False, persist_git_config=True)
    assert rb_receipt["enabled"] is False
    assert rb_receipt["status"] == "rolled_back"
    assert is_operational_store_enabled(repo) is False
    assert _clean_primary_admission_check(repo)[0] is True


def test_round_trip_same_ticket_across_primary_delivery_worktree_and_api(
    tmp_path: Path, monkeypatch
) -> None:
    """AC-04: Primary checkout, linked delivery worktree, and FastAPI app share the operational store."""
    repo = _init_tracked_planfile_repo(tmp_path)
    PlanfileStore(repo).enable_operational_intake(persist_git_config=True)

    worktree = repo / ".worktrees" / "ticket-001--delivery"
    _git(repo, "worktree", "add", "-b", "ticket/001-delivery", str(worktree), "main")

    # 1. Create ticket from primary checkout
    pf_primary = Planfile(str(repo))
    created = pf_primary.create_ticket("Cross-worktree round-trip ticket", priority="high")
    assert created.id == "PLF-034"

    # 2. Claim and update the same ticket from the linked delivery worktree
    assert canonical_project_root(worktree) == worktree.resolve()
    pf_worktree = Planfile(str(worktree))
    assert pf_worktree.store.operational_mode is True
    assert pf_worktree.store.base_dir == pf_primary.store.base_dir

    from_wt = pf_worktree.get_ticket("PLF-034")
    assert from_wt is not None
    assert from_wt.name == "Cross-worktree round-trip ticket"

    started = pf_worktree.start_ticket("PLF-034", assigned_to="agent:delivery", actor="agent:delivery")
    assert started is not None
    assert started.status.value == "in_progress"

    # 3. Read and complete the ticket through the configured FastAPI server
    monkeypatch.setattr(api_server, "get_planfile", lambda: Planfile(str(repo)))
    with TestClient(api_server.app) as client:
        resp = client.get("/tickets/PLF-034")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["id"] == "PLF-034"
        assert payload["status"] == "in_progress"
        assert payload["execution"]["assigned_to"] == "agent:delivery"

        complete_resp = client.post(
            "/tickets/PLF-034/complete",
            json={
                "note": "Verified across primary, worktree, and API",
                "actor": "validator",
                "expected_updated_at": payload["updated_at"],
            },
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "done"

    # 4. Verify primary checkout sees the completed state and both checkouts have clean tracked trees
    final_ticket = pf_primary.get_ticket("PLF-034")
    assert final_ticket is not None
    assert final_ticket.status.value == "done"
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert _git(worktree, "status", "--porcelain", "--untracked-files=all") == ""
