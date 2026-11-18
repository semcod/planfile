"""Tests for monotonic operation deadlines on scoped GitHub inbound sync."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
import requests
import typer
from typer.testing import CliRunner

from planfile.cli.groups.sync import commands as sync_commands
from planfile.cli.groups.sync import core as sync_core
from planfile.cli.groups.sync import register_sync_commands
from planfile.core.store import PlanfileStore, Ticket
from planfile.sync.deadline import (
    DEFAULT_INBOUND_TIMEOUT_SECONDS,
    SyncDeadline,
    SyncDeadlineExceededError,
    bind_backend_deadline,
    resolve_inbound_deadline,
)
from planfile.sync.operations import sync_from_external


@pytest.fixture(params=[False, True], ids=["yaml", "sharded"])
def ticket_store(tmp_path, request):
    store = PlanfileStore(tmp_path)
    store.init()
    store.create_ticket(
        Ticket(
            id="PLF-001",
            name="Scoped issue one",
            description="local baseline description",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={
                "github": {
                    "id": "101",
                    "url": "https://github.com/fixture/repo/issues/101",
                    "repository": "fixture/repo",
                }
            },
        )
    )
    store.create_ticket(
        Ticket(
            id="PLF-002",
            name="Scoped issue two",
            description="second baseline description",
            status="open",
            sprint="backlog",
            integration=["github"],
            sync={
                "github": {
                    "id": "102",
                    "url": "https://github.com/fixture/repo/issues/102",
                    "repository": "fixture/repo",
                }
            },
        )
    )
    if request.param:
        store.migrate_to_sharded_yaml()
    return store


def _remote_ticket(issue_id: str, title: str, description: str, status: str = "closed"):
    return SimpleNamespace(
        id=issue_id,
        name=title,
        description=description,
        status=status,
        assignee=None,
        labels=[],
        metadata={"state_reason": "completed"} if status == "closed" else {},
        key=None,
        url=f"https://github.com/fixture/repo/issues/{issue_id}",
    )


def _extract_deadline_json(output: str) -> dict:
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.startswith("{") and "sync_deadline_exceeded" in candidate:
            return json.loads(candidate)
    raise AssertionError(f"Expected single-line JSON diagnostic in output, got:\n{output}")


def test_resolve_inbound_deadline_precedence_and_validation(monkeypatch):
    monkeypatch.delenv("PLANFILE_SYNC_TIMEOUT_SECONDS", raising=False)
    default_deadline = resolve_inbound_deadline()
    assert default_deadline.timeout_seconds == DEFAULT_INBOUND_TIMEOUT_SECONDS

    monkeypatch.setenv("PLANFILE_SYNC_TIMEOUT_SECONDS", "12.5")
    env_deadline = resolve_inbound_deadline()
    assert env_deadline.timeout_seconds == 12.5

    backend = SimpleNamespace(config={"repo": "fixture/repo", "sync_timeout_seconds": 7.5})
    config_deadline = resolve_inbound_deadline(backend=backend)
    assert config_deadline.timeout_seconds == 7.5

    explicit_deadline = resolve_inbound_deadline(timeout_seconds=2.5, backend=backend)
    assert explicit_deadline.timeout_seconds == 2.5

    for invalid in (0, -1, float("nan"), float("inf"), True, "not-a-number"):
        with pytest.raises(ValueError):
            resolve_inbound_deadline(timeout_seconds=invalid)

    monkeypatch.setenv("PLANFILE_SYNC_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValueError):
        resolve_inbound_deadline()


def test_cli_slow_provider_exits_nonzero_with_json_and_preserves_cas_and_lease(
    ticket_store, monkeypatch
):
    ticket_store.update_ticket(
        "PLF-001",
        execution={
            "state": "running",
            "assigned_to": "agent:devin",
            "lease_expires_at": "2099-01-01T00:00:00Z",
        },
    )
    before = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-001", repair_index=False)

    class HangingBackend:
        config = {"repo": "fixture/repo"}

        def list_selected_tickets(self, selected_remote_ids, **kwargs):
            time.sleep(0.35)
            return [_remote_ticket("101", "Scoped issue one", "remote overwrite attempt")]

        def list_tickets(self, **kwargs):  # pragma: no cover
            raise AssertionError("full enumeration should not run for --ticket PLF-001")

    monkeypatch.setattr(sync_core, "_initialize_backend", lambda *args, **kwargs: HangingBackend())

    cli = typer.Typer()
    register_sync_commands(cli)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sync",
            "github",
            str(ticket_store.project_dir),
            "--direction",
            "from",
            "--ticket",
            "PLF-001",
            "--repo",
            "fixture/repo",
            "--timeout",
            "0.25",
        ],
    )

    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit)
    payload = _extract_deadline_json(result.output)
    assert payload["error"] == "sync_deadline_exceeded"
    assert payload["stage"] == "provider_fetch"
    assert payload["timeout_seconds"] == pytest.approx(0.25)
    assert payload["elapsed_seconds"] >= 0.25
    assert payload["completed_tickets"] == []
    assert payload["pending_tickets"] == ["101"]

    after = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-001", repair_index=False)
    assert after.updated_at == before.updated_at
    assert after.description == before.description
    assert "remote overwrite attempt" not in after.description
    assert after.status == "open"
    assert after.execution.state == "running"
    assert after.execution.assigned_to == "agent:devin"
    assert after.execution.lease_expires_at is not None
    assert after.execution.lease_expires_at == before.execution.lease_expires_at


def test_cli_scoped_ticket_closes_without_full_enumeration(ticket_store, monkeypatch):
    before_2 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-002", repair_index=False)
    seen_remote_ids: list[set[str]] = []

    class ScopedBackend:
        config = {"repo": "fixture/repo"}

        def list_selected_tickets(self, selected_remote_ids, **kwargs):
            seen_remote_ids.append(set(selected_remote_ids))
            return [_remote_ticket("101", "Scoped issue one", "updated via scoped fetch")]

        def list_tickets(self, **kwargs):  # pragma: no cover
            raise AssertionError("list_tickets enumeration must not be called")

    monkeypatch.setattr(sync_core, "_initialize_backend", lambda *args, **kwargs: ScopedBackend())

    cli = typer.Typer()
    register_sync_commands(cli)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "sync",
            "github",
            str(ticket_store.project_dir),
            "--direction",
            "from",
            "--ticket",
            "PLF-001",
            "--repo",
            "fixture/repo",
            "--timeout",
            "5.0",
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen_remote_ids == [{"101"}]
    plf_1 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-001", repair_index=False)
    plf_2 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-002", repair_index=False)
    assert plf_1.status == "done"
    assert plf_1.description == "updated via scoped fetch"
    assert plf_2.updated_at == before_2.updated_at
    assert plf_2.status == "open"
    assert plf_2.description == before_2.description


def test_deadline_uses_monotonic_clock_not_wall_clock_or_planfile_mtimes(
    ticket_store, monkeypatch
):
    mono_values = iter([100.0, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7])
    monkeypatch.setattr("planfile.sync.deadline.time.monotonic", lambda: next(mono_values, 100.7))
    monkeypatch.setattr("planfile.sync.deadline.time.time", lambda: (_ for _ in ()).throw(
        AssertionError("wall clock must not govern deadline")
    ))

    class TouchingBackend:
        config = {"repo": "fixture/repo"}

        def list_selected_tickets(self, selected_remote_ids, **kwargs):
            # Simulate unrelated file-system mtime changes inside .planfile/.
            scratch = ticket_store.project_dir / ".planfile" / "unrelated-touch.tmp"
            scratch.write_text("touch", encoding="utf-8")
            scratch.unlink()
            return [_remote_ticket("101", "Scoped issue one", "monotonic ok")]

    sync_from_external(
        TouchingBackend(),
        ticket_store,
        False,
        "github",
        ticket_ids=["PLF-001"],
        timeout_seconds=1.5,
    )
    updated = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-001", repair_index=False)
    assert updated.description == "monotonic ok"


def test_bind_backend_deadline_clamps_requester_timeout_and_converts_readtimeout(monkeypatch):
    ticks = iter([50.0, 50.1, 50.2, 52.5, 52.5])
    monkeypatch.setattr("planfile.sync.deadline.time.monotonic", lambda: next(ticks, 52.5))

    inner_requester = SimpleNamespace(_Requester__timeout=15)
    identity_requester = SimpleNamespace(_Requester__timeout=15)
    observed_timeouts: list[float] = []

    class DummyRepo:
        def __init__(self, req):
            self._requester = req

        def get_issue(self, number: int):
            observed_timeouts.append(self._requester._requester._Requester__timeout)
            raise requests.exceptions.ReadTimeout("socket read timed out")

    cached_requester = SimpleNamespace(_requester=inner_requester)
    backend = SimpleNamespace(
        config={"repo": "fixture/repo"},
        _identity_requester=identity_requester,
        github=SimpleNamespace(_Github__requester=cached_requester, requester=cached_requester),
        repo=DummyRepo(cached_requester),
    )

    deadline = SyncDeadline(timeout_seconds=2.0)
    with pytest.raises(SyncDeadlineExceededError) as exc_info:
        with bind_backend_deadline(backend, deadline):
            assert inner_requester._Requester__timeout == pytest.approx(1.9)
            assert identity_requester._Requester__timeout == pytest.approx(1.9)
            backend.repo.get_issue(101)

    assert exc_info.value.stage == "repository_identity"
    assert exc_info.value.elapsed_seconds == pytest.approx(2.5)
    assert observed_timeouts == [pytest.approx(1.8)]
    # Requester timeouts are always restored when leaving the context manager.
    assert inner_requester._Requester__timeout == 15
    assert identity_requester._Requester__timeout == 15


def test_fast_non_deadline_timeout_still_raises_sync_inbound_fetch_failed(ticket_store):
    class FastFailingBackend:
        config = {"repo": "fixture/repo"}

        def list_selected_tickets(self, selected_remote_ids, **kwargs):
            raise TimeoutError("selected provider failure")

    with pytest.raises(RuntimeError, match="sync_inbound_fetch_failed") as exc_info:
        sync_from_external(
            FastFailingBackend(),
            ticket_store,
            False,
            "github",
            ticket_ids=["PLF-001"],
            timeout_seconds=60.0,
        )
    assert isinstance(exc_info.value.__cause__, TimeoutError)


def test_local_projection_deadline_partial_completion_and_convergent_retry(
    ticket_store, monkeypatch
):
    before_2 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-002", repair_index=False)
    now = {"value": 10.0}
    monkeypatch.setattr("planfile.sync.deadline.time.monotonic", lambda: now["value"])

    orig_update = ticket_store.update_ticket

    def advancing_update(ticket_id, *args, **kwargs):
        result = orig_update(ticket_id, *args, **kwargs)
        if ticket_id == "PLF-001":
            now["value"] = 12.0  # Exceed 1.0s deadline right after persisting PLF-001.
        return result

    monkeypatch.setattr(ticket_store, "update_ticket", advancing_update)

    class TwoTicketBackend:
        config = {"repo": "fixture/repo"}

        def list_selected_tickets(self, selected_remote_ids, **kwargs):
            assert selected_remote_ids == {"101", "102"}
            return [
                _remote_ticket("101", "Scoped issue one", "remote one updated"),
                _remote_ticket("102", "Scoped issue two", "remote two updated"),
            ]

    with pytest.raises(SyncDeadlineExceededError) as exc_info:
        sync_from_external(
            TwoTicketBackend(),
            ticket_store,
            False,
            "github",
            ticket_ids=["PLF-001", "PLF-002"],
            timeout_seconds=1.0,
        )

    assert exc_info.value.stage == "local_projection"
    assert exc_info.value.completed_tickets == ("101",)
    assert exc_info.value.pending_tickets == ("102",)

    mid_1 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-001", repair_index=False)
    mid_2 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-002", repair_index=False)
    assert mid_1.description == "remote one updated"
    assert mid_2.updated_at == before_2.updated_at
    assert mid_2.description == before_2.description

    # Convergent retry completes the remaining pending ticket cleanly.
    monkeypatch.setattr(ticket_store, "update_ticket", orig_update)
    sync_from_external(
        TwoTicketBackend(),
        ticket_store,
        False,
        "github",
        ticket_ids=["PLF-001", "PLF-002"],
        timeout_seconds=5.0,
    )
    done_1 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-001", repair_index=False)
    done_2 = PlanfileStore(ticket_store.project_dir).get_ticket("PLF-002", repair_index=False)
    assert done_1.description == "remote one updated"
    assert done_2.description == "remote two updated"


def test_github_cmd_direct_python_call_preserves_legacy_kwargs_without_timeout(monkeypatch):
    captured: list[tuple[tuple, dict]] = []

    def fake_sync_integration(*args, **kwargs):
        captured.append((args, kwargs))

    monkeypatch.setattr(sync_commands, "sync_integration", fake_sync_integration)
    sync_commands.github_cmd(directory=".", dry_run=True, direction="from")

    assert len(captured) == 1
    args, kwargs = captured[0]
    assert args == ("github", ".", True, "from")
    assert "timeout_seconds" not in kwargs
