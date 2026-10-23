"""The repository schedule observes closure through an inbound-only adapter."""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import typer
import yaml
from typer.testing import CliRunner

from planfile.cli.groups.sync import commands
from planfile.integrations.config import IntegrationConfig
from planfile.sync.base import TicketState

ROOT = Path(__file__).resolve().parents[1]


class ReadOnlyBackend:
    config = {"repo": "semcod/planfile"}

    def __init__(self):
        self.reads = 0
        self.mutations = []

    def list_tickets(self, **kwargs):
        assert kwargs == {"labels": ["planfile", "managed"]}
        self.reads += 1
        rows = [
            TicketState(
                id=str(number),
                key=f"semcod/planfile#{number}",
                name=f"Human tracker title {number}",
                description="Remote evidence",
                status="closed",
                url=f"https://github.com/semcod/planfile/issues/{number}",
                metadata={"state_reason": "not_planned" if number in (9, 13) else "completed"},
            )
            for number in (3, 9, 13, 14, 15)
        ]
        return rows + [TicketState(id="99999", name="Unselected", status="open")]

    def create_ticket(self, *args, **kwargs):
        self.mutations.append("create")
        raise AssertionError("The observer tried to create an Issue")

    def update_ticket(self, *args, **kwargs):
        self.mutations.append("update")
        raise AssertionError("The observer tried to change tracker metadata/state")

    def add_comment(self, *args, **kwargs):
        self.mutations.append("comment")
        raise AssertionError("The observer tried to publish a comment")


@pytest.fixture
def observer(monkeypatch):
    path = ROOT / ".github/scripts/observe_planfile_terminal_issues.py"
    spec = importlib.util.spec_from_file_location("scheduled_observer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("GITHUB_REPOSITORY", module.REPOSITORY)
    monkeypatch.setenv("GITHUB_SHA", module.git_head(ROOT))
    # Unit fixtures use the candidate working-tree inputs. Production reads only
    # exact Git blobs, which the hosted canary binds to the merged run SHA.
    monkeypatch.setattr(module, "source_blob", lambda root, name: (root / name).read_bytes())
    snapshot = {
        ident: {
            "number": number,
            "state": "closed",
            "state_reason": "not_planned" if status == "canceled" else "completed",
            "metadata_sha256": "a" * 64,
        }
        for ident, (number, status) in module.SELECTION.items()
    }
    monkeypatch.setattr(module, "remote_snapshot", lambda repo: copy.deepcopy(snapshot))
    backend = ReadOnlyBackend()
    monkeypatch.setattr(IntegrationConfig, "get_integration_backend", lambda *a, **k: backend)
    app = typer.Typer()
    app.command("github")(commands.github_cmd)
    app.command("noop")(lambda: None)

    def run_existing_cli(command):
        assert command[:4] == [sys.executable, "-m", "planfile", "sync"]
        result = CliRunner().invoke(app, command[4:])
        assert result.exit_code == 0, result.output + repr(result.exception)

    monkeypatch.setattr(module, "invoke_cli", run_existing_cli)
    return module, backend, snapshot


def test_stale_canary_runs_real_adapter_dry_real_repeat_without_remote_writes(observer):
    module, backend, _ = observer
    result = module.observe(ROOT, canary=True, observation_id="unit-stale-closed")
    assert result["result"] == "PASS"
    assert [run["phase"] for run in result["runs"]] == ["dry-run", "real", "repeat"]
    assert set(result["selection"]) == set(module.SELECTION)
    assert set(result["runs"][0]["local_statuses"].values()) == {"open"}
    assert result["runs"][1]["local_statuses"] == result["runs"][2]["local_statuses"]
    assert result["remote_before"] == result["remote_after"]
    assert backend.reads == 3
    assert backend.mutations == []


def test_scheduled_run_uses_one_real_inbound_observation(observer):
    module, backend, _ = observer
    result = module.observe(ROOT, canary=False, observation_id="unit-scheduled")
    assert [run["phase"] for run in result["runs"]] == ["real"]
    assert backend.reads == 1
    assert backend.mutations == []


def test_observer_refuses_a_remote_issue_that_was_reopened(observer):
    module, backend, snapshot = observer
    snapshot["GITHUB-3"]["state"] = "open"
    with pytest.raises(ValueError, match="remote_no_longer_terminal"):
        module.observe(ROOT, canary=True, observation_id="unit-reopened")
    assert backend.reads == 0
    assert backend.mutations == []


def test_observer_detects_remote_metadata_change(observer, monkeypatch):
    module, backend, snapshot = observer
    replies = [copy.deepcopy(snapshot), copy.deepcopy(snapshot)]
    replies[1]["GITHUB-3"]["metadata_sha256"] = "b" * 64
    monkeypatch.setattr(module, "remote_snapshot", lambda repo: replies.pop(0))
    with pytest.raises(ValueError, match="remote_metadata_or_state_changed"):
        module.observe(ROOT, canary=True, observation_id="unit-metadata")
    assert backend.mutations == []


def test_observer_requires_canonical_ids_before_reconciling(observer, monkeypatch):
    module, backend, _ = observer

    def missing_identity(root, name):
        raw = (root / name).read_bytes()
        if name == ".planfile/sprints/backlog.yaml":
            data = yaml.safe_load(raw)
            data["sprint"]["tickets"]["GITHUB-3"].pop("id")
            return yaml.safe_dump(data, sort_keys=False).encode()
        return raw

    monkeypatch.setattr(module, "source_blob", missing_identity)
    with pytest.raises(ValueError, match="qualified_identity_missing"):
        module.observe(ROOT, canary=True, observation_id="unit-legacy")
    assert backend.reads == 0
    assert backend.mutations == []


@pytest.mark.parametrize(
    ("variable", "value", "error"),
    [
        ("GITHUB_REPOSITORY", "other/repository", "repository_scope"),
        ("GITHUB_SHA", "0" * 40, "source_revision_mismatch"),
    ],
)
def test_observer_binds_repository_and_source(observer, monkeypatch, variable, value, error):
    module, backend, _ = observer
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match=error):
        module.observe(ROOT, canary=True, observation_id="unit-binding")
    assert backend.reads == 0
    assert backend.mutations == []


def test_qualified_source_records_retain_their_stable_native_identity(observer):
    module, _, _ = observer
    records = module.inventory(ROOT)
    for ident, (number, expected) in module.SELECTION.items():
        row = records[ident]
        assert row["id"] == ident
        assert row["status"] == expected
        assert row["history"][-1]["metadata"]["issue"] == number
        assert row["history"][-1]["metadata"]["repository"] == module.REPOSITORY


def test_scheduled_caller_and_callee_have_only_read_authority_and_locked_source():
    caller = yaml.load(
        (ROOT / ".github/workflows/planfile-github-sync.yml").read_text(), Loader=yaml.BaseLoader
    )
    callee = yaml.load(
        (ROOT / ".github/workflows/planfile-sync-readonly.yml").read_text(), Loader=yaml.BaseLoader
    )
    for workflow in (caller, callee):
        assert workflow["permissions"] == {"contents": "read", "issues": "read"}
        for job in workflow["jobs"].values():
            assert job["permissions"] == {"contents": "read", "issues": "read"}
    assert caller["jobs"]["sync"]["uses"] == "./.github/workflows/planfile-sync-readonly.yml"
    assert caller["on"]["schedule"] == [{"cron": "17 * * * *"}]
    assert "workflow_dispatch" in callee["on"]
    steps = callee["jobs"]["observe"]["steps"]
    assert all(
        re.fullmatch(r"[^@]+@[a-f0-9]{40}", step["uses"]) for step in steps if "uses" in step
    )
    assert steps[0]["with"]["persist-credentials"] == "false"
    runs = [step["run"] for step in steps if "run" in step]
    assert any("uv==0.11.30" in run for run in runs)
    assert any("uv sync --locked --no-dev" in run for run in runs)
    assert any("uv run --no-sync python" in run for run in runs)
    # The older general adapter still supports its original bidirectional use.
    legacy = (ROOT / ".github/workflows/planfile-sync-reusable.yml").read_text()
    assert "--direction both" in legacy
