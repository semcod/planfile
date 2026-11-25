"""Tests for target-repository-aware ``in_progress`` reconciliation (AUT-14 / #346)."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typer.testing import CliRunner

from planfile import (
    RECONCILE_REPORT_SCHEMA,
    Planfile,
    TicketExecution,
    TicketSource,
    reconcile_fleet_in_progress,
    reconcile_in_progress,
)
from planfile.cli.commands import _build_app


def _git(cwd: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_AUTHOR_NAME", "Test Bot")
    env.setdefault("GIT_AUTHOR_EMAIL", "bot@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "Test Bot")
    env.setdefault("GIT_COMMITTER_EMAIL", "bot@example.com")
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.stdout.strip()


def _init_git_repo(repo: Path, remote_slug: str = "semcod/demo") -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "remote", "add", "origin", f"https://github.com/{remote_slug}.git")
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "Initial commit")
    return _git(repo, "rev-parse", "HEAD")


def _write_lease(
    repo: Path,
    filename: str,
    *,
    ticket_id: str,
    phase: str = "editing",
    expires_at: str,
    owner_actor: str = "agent:codex",
    owner_session: str = "session-1",
    worktree_id: str | None = None,
) -> None:
    leases_dir = repo / ".subactor" / "leases"
    leases_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "wellmanifest.change-lease/v1",
        "leaseId": f"lease-{ticket_id}",
        "repositoryRef": "semcod/demo",
        "targetBranch": "main",
        "ticketId": ticket_id,
        "workstream": "application",
        "scopeHash": "a" * 64,
        "branchRef": f"refs/heads/ticket/{ticket_id}",
        "worktreeId": worktree_id or f"{ticket_id}--work",
        "ownerActor": owner_actor,
        "ownerSession": owner_session,
        "phase": phase,
        "leaseRevision": 1,
        "fencingToken": 1,
        "issuedAt": "2026-11-15T10:00:00Z",
        "expiresAt": expires_at,
        "heartbeatAt": "2026-11-15T10:00:00Z",
        "headSha": "b" * 40,
        "pullRequest": None,
        "validatorRunId": None,
        "publicationFrozen": False,
        "planHash": "c" * 64,
        "previousReceiptRef": None,
        "eventSequence": 1,
    }
    (leases_dir / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_reconcile_merged_terminal_receipt_closes_ticket_with_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    pf = Planfile(repo)
    ticket = pf.create_ticket(name="Ship feature", labels=["ticket-010"])
    pf.start_ticket(ticket.id, assigned_to="agent:worker")

    # Simulate merged commit on main + terminal receipt
    ticket_dir = repo / "project" / "ticket-010"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "README.md").write_text(
        f"# Ticket 010\n\n- **Planfile**: {ticket.id}\n",
        encoding="utf-8",
    )
    _git(repo, "add", "project/ticket-010/README.md")
    _git(repo, "commit", "-m", "Merge ticket-010")
    merged_sha = _git(repo, "rev-parse", "HEAD")

    receipts_dir = repo / ".git" / "new-project"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (receipts_dir / "terminal-receipts.json").write_text(
        json.dumps(
            {
                "schema": "new-project.terminal-receipt-registry/v1",
                "receipts": [
                    {
                        "ticket": "ticket-010",
                        "outcome": "merged",
                        "headSha": merged_sha,
                        "terminalSha": merged_sha,
                        "targetBranch": "main",
                        "receiptRef": "receipt:github-pr:semcod/demo:42",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # Dry-run by default: reports merged -> done without mutating storage
    dry_report = reconcile_in_progress(pf)
    assert dry_report["schema"] == RECONCILE_REPORT_SCHEMA
    assert dry_report["mode"] == "dry_run"
    assert dry_report["counts"]["merged_to_done"] == 1
    assert dry_report["counts"]["applied"] == 0
    decision = dry_report["decisions"][0]
    assert decision["classification"] == "merged"
    assert decision["proposed_status"] == "done"
    assert decision["terminalReceiptRef"] == "receipt:github-pr:semcod/demo:42"
    assert decision["terminalSha"] == merged_sha
    assert pf.get_ticket(ticket.id).status.value == "in_progress"

    # --apply mutates atomically and records merge receipt evidence
    apply_report = pf.reconcile_in_progress(apply=True)
    assert apply_report["mode"] == "apply"
    assert apply_report["counts"]["merged_to_done"] == 1
    assert apply_report["counts"]["applied"] == 1

    closed = pf.get_ticket(ticket.id)
    assert closed is not None
    assert closed.status.value == "done"
    assert closed.execution is not None and closed.execution.state == "done"
    assert closed.outputs is not None and closed.outputs.completion_receipt is not None
    assert closed.outputs.completion_receipt["terminalReceiptRef"] == "receipt:github-pr:semcod/demo:42"
    assert closed.outputs.completion_receipt["terminalSha"] == merged_sha


def test_reconcile_rejects_unverified_non_ancestor_terminal_sha(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    pf = Planfile(repo)
    ticket = pf.create_ticket(name="Unmerged branch work", labels=["ticket-011"])
    pf.start_ticket(ticket.id, assigned_to="agent:worker")

    # Create commit on an unmerged side branch, NOT on main
    _git(repo, "checkout", "-b", "side-work")
    (repo / "side.txt").write_text("unmerged\n", encoding="utf-8")
    _git(repo, "add", "side.txt")
    _git(repo, "commit", "-m", "Side commit")
    side_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")

    receipts_dir = repo / ".git" / "new-project"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (receipts_dir / "terminal-receipts.json").write_text(
        json.dumps(
            {
                "schema": "new-project.terminal-receipt-registry/v1",
                "receipts": [
                    {
                        "ticket": "ticket-011",
                        "outcome": "merged",
                        "headSha": side_sha,
                        "terminalSha": side_sha,
                        "targetBranch": "main",
                        "receiptRef": "receipt:forged:99",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = reconcile_in_progress(pf, apply=True)
    assert report["counts"]["merged_to_done"] == 0
    assert report["counts"]["abandoned_to_open"] == 1
    reopened = pf.get_ticket(ticket.id)
    assert reopened is not None and reopened.status.value == "open"


def test_reconcile_live_lease_and_active_worktree_vs_abandoned(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    base_sha = _init_git_repo(repo)
    now = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
    future_iso = (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    past_iso = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")

    pf = Planfile(repo)

    # 1. Ticket bound to a live non-expired .subactor lease -> stays in_progress
    t_leased = pf.create_ticket(name="Leased work", labels=["ticket-020"])
    pf.start_ticket(t_leased.id, assigned_to="agent:codex")
    _write_lease(
        repo,
        "ticket-020--leased.json",
        ticket_id="ticket-020",
        expires_at=future_iso,
        owner_actor="agent:codex",
    )

    # 2. Ticket with expired lease BUT dirty canonical worktree -> stays in_progress
    t_worktree = pf.create_ticket(name="Dirty worktree work", labels=["ticket-021"])
    pf.start_ticket(t_worktree.id, assigned_to="agent:codex")
    _write_lease(
        repo,
        "ticket-021--dirty.json",
        ticket_id="ticket-021",
        expires_at=past_iso,
        owner_actor="agent:codex",
    )
    wt_path = repo / ".worktrees" / "ticket-021--dirty"
    _git(repo, "worktree", "add", "-b", "ticket/021-dirty", str(wt_path), base_sha)
    (wt_path / "wip.py").write_text("x = 1\n", encoding="utf-8")

    # 3. Abandoned ticket (same generic actor 'agent:codex', but no bound lease/worktree!)
    t_abandoned = pf.create_ticket(name="Abandoned work")
    pf.start_ticket(t_abandoned.id, assigned_to="agent:codex")

    # Dry-run first
    dry = reconcile_in_progress(pf, now=now)
    assert dry["counts"]["active_retained"] == 2
    assert dry["counts"]["abandoned_to_open"] == 1
    assert pf.get_ticket(t_abandoned.id).status.value == "in_progress"

    # Apply
    applied = reconcile_in_progress(pf, apply=True, now=now)
    assert applied["counts"]["active_retained"] == 2
    assert applied["counts"]["abandoned_to_open"] == 1
    assert applied["counts"]["applied"] == 1

    assert pf.get_ticket(t_leased.id).status.value == "in_progress"
    assert pf.get_ticket(t_worktree.id).status.value == "in_progress"

    reopened = pf.get_ticket(t_abandoned.id)
    assert reopened is not None
    assert reopened.status.value == "open"
    assert reopened.execution is not None
    assert reopened.execution.state == "ready"
    assert reopened.execution.assigned_to is None
    assert reopened.execution.lease_expires_at is None
    assert reopened.execution.started_at is None


def test_reconcile_preserves_unobserved_target_repositories(tmp_path: Path) -> None:
    # Case A: Git repo with a ticket referencing an unobservable external repo
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    pf = Planfile(repo)
    t_external = pf.create_ticket(
        name="Remote repo ticket",
        source=TicketSource(
            tool="heyasa",
            context={"repository": "other-org/missing-local-checkout"},
        ),
    )
    pf.start_ticket(t_external.id, assigned_to="agent:remote")

    report = reconcile_in_progress(pf, apply=True, workspace_root=tmp_path)
    assert report["counts"]["unobserved_preserved"] == 1
    assert report["counts"]["applied"] == 0
    assert report["decisions"][0]["classification"] == "unobserved"
    assert pf.get_ticket(t_external.id).status.value == "in_progress"

    # Case B: Non-git directory cannot observe worktrees/receipts -> preserved as unobserved
    non_git = tmp_path / "non_git_project"
    non_git.mkdir()
    pf_non_git = Planfile(non_git)
    t_local = pf_non_git.create_ticket(name="Non-git in_progress")
    pf_non_git.start_ticket(t_local.id, assigned_to="agent:local")

    ng_report = reconcile_in_progress(pf_non_git, apply=True)
    assert ng_report["counts"]["unobserved_preserved"] == 1
    assert pf_non_git.get_ticket(t_local.id).status.value == "in_progress"


def test_reconcile_cli_and_fleet_json(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    repo_a = ws / "semcod" / "alpha"
    _init_git_repo(repo_a, remote_slug="semcod/alpha")
    pf_a = Planfile(repo_a)
    t1 = pf_a.create_ticket(name="Stale alpha task")
    pf_a.update_ticket(
        t1.id,
        status="in_progress",
        execution=TicketExecution(state="running", assigned_to="old-worker"),
    )

    runner = CliRunner()
    root_app = _build_app(ticket_only=False)
    ticket_only_app = _build_app(ticket_only=True)

    res_dry = runner.invoke(
        root_app,
        ["reconcile", "--project", str(repo_a), "--format", "json"],
    )
    assert res_dry.exit_code == 0, res_dry.output
    payload_dry = json.loads(res_dry.stdout)
    assert payload_dry["mode"] == "dry_run"
    assert payload_dry["counts"]["abandoned_to_open"] == 1
    assert pf_a.get_ticket(t1.id).status.value == "in_progress"

    res_apply = runner.invoke(
        ticket_only_app,
        ["ticket", "reconcile", "--project", str(repo_a), "--apply", "--format", "json"],
    )
    assert res_apply.exit_code == 0, res_apply.output
    payload_apply = json.loads(res_apply.stdout)
    assert payload_apply["mode"] == "apply"
    assert payload_apply["counts"]["applied"] == 1
    assert pf_a.get_ticket(t1.id).status.value == "open"

    # Fleet reconciliation check
    fleet_report = reconcile_fleet_in_progress(ws, apply=False)
    assert fleet_report["counts"]["repositories_scanned"] == 1
    assert fleet_report["counts"]["scanned_in_progress"] == 0


def test_local_reconciliation_skips_workspace_index(tmp_path, monkeypatch):
    from planfile import reconcile

    repo = tmp_path / "local-project"
    _init_git_repo(repo)
    pf = Planfile(repo)
    ticket = pf.create_ticket(name="Recover local job")
    pf.start_ticket(ticket.id, assigned_to="agent:test")

    def unexpected_scan(*args, **kwargs):
        raise AssertionError("A local reconciliation should not observe unrelated repositories")

    monkeypatch.setattr(reconcile, "discover_planfile_repositories", unexpected_scan)
    report = reconcile_in_progress(pf, workspace_root=tmp_path)
    assert [item["id"] for item in report["decisions"]] == [ticket.id]
    assert pf.get_ticket(ticket.id).status.value == "in_progress"
