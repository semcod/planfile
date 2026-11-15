"""Tests for the canonical ``planfile.executable-queue/v1`` specification & evaluator (AUT-14 / #346)."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typer.testing import CliRunner

from planfile import (
    EXECUTABLE_QUEUE_SCHEMA,
    Planfile,
    TicketExecution,
    TicketSource,
    evaluate_executable_candidate,
    executable_queue,
    executable_skip_reason,
    fleet_executable_queue,
    is_executable_candidate,
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


def _init_git_repo(repo: Path, remote_slug: str = "semcod/demo") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "remote", "add", "origin", f"https://github.com/{remote_slug}.git")
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "Initial commit")


def _write_live_lease(repo: Path, ticket_id: str, expires_at: str) -> None:
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
        "worktreeId": f"{ticket_id}--work",
        "ownerActor": "agent:codex",
        "ownerSession": "session-live",
        "phase": "editing",
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
    (leases_dir / f"{ticket_id}--work.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_executable_queue_contract_predicates_and_ordering(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CURRENT_GOAL", raising=False)
    monkeypatch.delenv("PLANFILE_NO_AUTONOMY_FILTER", raising=False)
    monkeypatch.delenv("PLANFILE_REQUIRE_PROCESS_ENVELOPE", raising=False)

    repo = tmp_path / "repo"
    _init_git_repo(repo, remote_slug="semcod/planfile")
    pf = Planfile(repo)
    now = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
    future_iso = (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    # Satisfied dependency in current sprint
    dep_done = pf.create_ticket(name="Completed prerequisite")
    pf.complete_ticket(dep_done.id, note="Done")

    # Satisfied dependency archived in history-* sprint
    dep_archived = pf.create_ticket(name="Archived prerequisite", sprint="history-2026-10-01")
    pf.complete_ticket(dep_archived.id, note="Archived done")

    # Unsatisfied dependency (still open)
    dep_open = pf.create_ticket(name="Open blocker", priority="low")

    # Executable candidates across current + backlog (test ordering: high bug > high feature > normal > low)
    cand_feature_high = pf.create_ticket(
        name="High feature with resolved deps",
        priority="high",
        blocked_by=[dep_done.id, dep_archived.id],
    )
    cand_bug_high = pf.create_ticket(
        name="High priority bug",
        priority="high",
        labels=["bug"],
    )
    cand_backlog = pf.create_ticket(
        name="Backlog ready task",
        priority="normal",
        sprint="backlog",
    )

    # Excluded tickets:
    # 1. Blocked by open dependency
    excl_dep = pf.create_ticket(name="Blocked by open ticket", blocked_by=[dep_open.id])
    # 2.Blocked by missing dependency
    excl_missing_dep = pf.create_ticket(name="Blocked by missing", blocked_by=["PLF-99999"])
    # 3. Autonomy / human-gated
    excl_frontier = pf.create_ticket(name="Frontier task", labels=["autonomy-frontier"])
    excl_human = pf.create_ticket(name="Human task", labels=["actor:human"])
    excl_waiting = pf.create_ticket(name="Waiting on GPU", labels=["waiting:gpu"])
    # 4. Non-ready execution state (waiting_input)
    excl_waiting_input = pf.create_ticket(name="Needs input")
    pf.update_ticket(
        excl_waiting_input.id,
        execution=TicketExecution(state="waiting_input"),
    )
    # 5. Non-open status (in_progress & blocked)
    excl_in_progress = pf.create_ticket(name="Currently running")
    pf.start_ticket(excl_in_progress.id, assigned_to="agent:worker")
    excl_blocked_status = pf.create_ticket(name="Explicitly blocked", sprint="backlog")
    pf.block_ticket(excl_blocked_status.id, reason="External outage")
    # 6. Invalid / unobservable target repository
    excl_bad_repo = pf.create_ticket(
        name="Missing repo target",
        source=TicketSource(
            tool="heyasa",
            context={"repository": "ghost-org/missing-repo"},
        ),
    )
    # 7. Open ticket held by an active non-expired .subactor writer lease
    excl_leased = pf.create_ticket(name="Held by live lease", labels=["ticket-050"])
    _write_live_lease(repo, "ticket-050", expires_at=future_iso)
    # 8. Open ticket held by live Planfile claim lease
    excl_pf_leased = pf.create_ticket(name="Claimed in Planfile")
    pf.update_ticket(
        excl_pf_leased.id,
        execution=TicketExecution(
            state="ready",
            assigned_to="koru-1",
            lease_expires_at=now + timedelta(minutes=30),
        ),
    )
    # 9. Historical open ghost in history-* sprint must not leak into active queue
    ghost_history = pf.create_ticket(name="History ghost", sprint="history-2026-10-01")

    report = pf.executable_queue(now=now, workspace_root=tmp_path)
    assert report["schema"] == EXECUTABLE_QUEUE_SCHEMA
    assert report["repository"] == "semcod/planfile"

    expected_order = [
        cand_bug_high.id,
        cand_feature_high.id,
        cand_backlog.id,
        dep_open.id,
    ]
    assert report["candidate_ids"] == expected_order
    assert report["counts"]["executable"] == 4

    skipped_by_id = {item["id"]: item for item in report["skipped"]}
    assert skipped_by_id[excl_dep.id]["reason"] == f"blocked_by:{dep_open.id}"
    assert skipped_by_id[excl_missing_dep.id]["reason"] == "blocked_by:PLF-99999"
    assert skipped_by_id[excl_frontier.id]["reason"] == "autonomy-frontier"
    assert skipped_by_id[excl_human.id]["reason"] == "actor:human"
    assert skipped_by_id[excl_waiting.id]["reason"] == "waiting:gpu"
    assert skipped_by_id[excl_waiting_input.id]["reason"] == "exec_state:waiting_input"
    assert skipped_by_id[excl_in_progress.id]["reason"] == "status:in_progress"
    assert skipped_by_id[excl_blocked_status.id]["reason"] == "status:blocked"
    assert "target_repository_unobserved" in skipped_by_id[excl_bad_repo.id]["reason"]
    assert skipped_by_id[excl_leased.id]["reason"] == "active_lease:lease-ticket-050"
    assert skipped_by_id[excl_pf_leased.id]["reason"] == f"active_lease:planfile:{excl_pf_leased.id}"
    assert ghost_history.id not in skipped_by_id
    assert ghost_history.id not in report["candidate_ids"]

    # Direct Python evaluator checks (both Ticket model and raw dict views)
    assert is_executable_candidate(cand_bug_high, pf=pf, now=now) is True
    assert executable_skip_reason(cand_bug_high, pf=pf, now=now) == ""
    assert is_executable_candidate(excl_leased, pf=pf, now=now) is False

    dict_view = {
        "id": "RAW-1",
        "name": "Raw dict ticket",
        "status": "open",
        "sprint": "history-2026-09-01",
    }
    eval_hist = evaluate_executable_candidate(dict_view, repo_path=repo, now=now)
    assert eval_hist.executable is False
    assert eval_hist.reason == "archived_sprint"


def test_fleet_executable_queue_and_cli_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CURRENT_GOAL", raising=False)
    monkeypatch.delenv("PLANFILE_NO_AUTONOMY_FILTER", raising=False)

    ws = tmp_path / "github"
    repo_one = ws / "semcod" / "one"
    repo_two = ws / "heyasa" / "two"
    _init_git_repo(repo_one, remote_slug="semcod/one")
    _init_git_repo(repo_two, remote_slug="heyasa/two")

    pf_one = Planfile(repo_one)
    pf_two = Planfile(repo_two)

    c1 = pf_one.create_ticket(name="Repo one ready", priority="high")
    s1 = pf_one.create_ticket(name="Repo one active")
    pf_one.start_ticket(s1.id, assigned_to="worker-1")

    c2 = pf_two.create_ticket(name="Repo two ready", priority="critical")

    fleet = fleet_executable_queue(ws)
    assert fleet["schema"] == EXECUTABLE_QUEUE_SCHEMA
    assert fleet["repositories_scanned"] == 2
    assert fleet["counts"]["executable"] == 2
    assert fleet["counts"]["in_progress"] == 1
    assert fleet["candidate_ids"] == [c2.id, c1.id]

    single = executable_queue(repo_one)
    assert single["schema"] == EXECUTABLE_QUEUE_SCHEMA
    assert single["candidate_ids"] == [c1.id]

    runner = CliRunner()
    root_app = _build_app(ticket_only=False)
    ticket_app = _build_app(ticket_only=True)

    res_fleet = runner.invoke(
        root_app,
        ["executable-queue", "--workspace-root", str(ws), "--fleet", "--format", "json"],
    )
    assert res_fleet.exit_code == 0, res_fleet.output
    cli_fleet = json.loads(res_fleet.stdout)
    assert cli_fleet["schema"] == EXECUTABLE_QUEUE_SCHEMA
    assert cli_fleet["candidate_ids"] == [c2.id, c1.id]

    res_ticket = runner.invoke(
        ticket_app,
        ["ticket", "executable-queue", "--project", str(repo_one), "--format", "json"],
    )
    assert res_ticket.exit_code == 0, res_ticket.output
    cli_single = json.loads(res_ticket.stdout)
    assert cli_single["candidate_ids"] == [c1.id]
