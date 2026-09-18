"""Offline regression coverage for outbound sync failures and safe retries."""

from dataclasses import asdict
from types import SimpleNamespace

import pytest
import typer
import yaml
from typer.testing import CliRunner

from planfile.cli.groups.sync import commands
from planfile.integrations.config import IntegrationConfig
from planfile.sync.outbound import sync_to_external
from planfile.sync.state import SyncState


class Backend:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.created = []
        self.updated = []
        self.fetched = False

    def create_ticket(self, ticket):
        ident = ticket["metadata"]["planfile_id"]
        self.created.append(ident)
        if ident in self.failures:
            raise RuntimeError("controlled offline create failure")
        return {"id": ident + "-remote", "url": "https://example.invalid/" + ident}

    def update_ticket(self, external_id, **fields):
        self.updated.append(external_id)
        if external_id in self.failures:
            raise RuntimeError("controlled offline update failure")

    def list_tickets(self):
        self.fetched = True
        return []


def source(tmp_path, names=("good", "bad", "later")):
    path = tmp_path / "tickets.planfile.yaml"
    tickets = {name: {"title": name, "integration": "github"} for name in names}
    data = {
        "project": {"name": "fixture/isolated"},
        "integrations": {"github": {"repo": "fixture/isolated"}},
        "backlog": {"tickets": tickets},
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    store = SimpleNamespace(base_dir=tmp_path / ".planfile")
    return path, data, store


def outbound(backend, path, data, store, dry_run=False):
    return sync_to_external(
        backend, list(data["backlog"]["tickets"].items()), dry_run, store, "github", path, data
    )


def test_partial_batch_saves_successes_before_raising_and_retries_without_create(tmp_path):
    path, data, store = source(tmp_path)
    backend = Backend({"bad"})
    with pytest.raises(RuntimeError, match="1 ticket") as caught:
        outbound(backend, path, data, store)
    assert asdict(caught.value.result) == {
        "succeeded": ("good", "later"),
        "created": ("good", "later"),
        "reused": (),
        "updated": (),
        "failed": ("bad",),
        "planned": (),
    }
    assert caught.value.result.to_dict()["succeeded"] == ["good", "later"]
    assert backend.created == ["good", "bad", "later"]
    saved = yaml.safe_load(path.read_text())
    assert saved["backlog"]["tickets"]["good"]["sync"]["github"]["id"] == "good-remote"
    assert "sync" not in saved["backlog"]["tickets"]["bad"]
    state = SyncState(store.base_dir, "github")
    assert state.get_remote_id("later") == "later-remote"
    assert state.get_remote_id("bad") is None

    retry = Backend()
    result = outbound(retry, path, saved, store)
    assert retry.created == ["bad"]
    assert retry.updated == ["good-remote", "later-remote"]
    assert result.failed == ()
    assert result.succeeded == ("good", "bad", "later")


def test_all_failures_are_visible(tmp_path):
    path, data, store = source(tmp_path, ("a", "b"))
    with pytest.raises(RuntimeError, match="2 ticket") as caught:
        outbound(Backend({"a", "b"}), path, data, store)
    assert caught.value.result.failed == ("a", "b")
    assert caught.value.result.succeeded == ()


def test_update_failure_retains_mapping_and_attempts_later_ticket(tmp_path):
    path, data, store = source(tmp_path, ("bad", "later"))
    state = SyncState(store.base_dir, "github")
    state.save_sync({"bad": "existing"})
    backend = Backend({"existing"})
    with pytest.raises(RuntimeError, match="1 ticket"):
        outbound(backend, path, data, store)
    assert backend.updated == ["existing"]
    assert backend.created == ["later"]
    assert state.get_remote_id("bad") == "existing"
    assert state.get_remote_id("later") == "later-remote"


def test_missing_remote_replacement_failure_is_not_success(tmp_path):
    path, data, store = source(tmp_path, ("bad",))

    class MissingBackend(Backend):
        def update_ticket(self, external_id, **fields):
            raise RuntimeError("404 Not Found")

    SyncState(store.base_dir, "github").save_sync({"bad": "missing"})
    with pytest.raises(RuntimeError, match="1 ticket"):
        outbound(MissingBackend({"bad"}), path, data, store)


def test_dry_run_does_not_write_or_call_backend(tmp_path):
    path, data, store = source(tmp_path)
    before = path.read_bytes()
    backend = Backend({"good", "bad", "later"})
    result = outbound(backend, path, data, store, dry_run=True)
    assert result.planned == ("good", "bad", "later")
    assert result.succeeded == result.failed == ()
    assert backend.created == backend.updated == []
    assert path.read_bytes() == before
    assert not store.base_dir.exists()


def test_rate_limit_stops_batch_after_current_ticket_and_preserves_success(tmp_path):
    path, data, store = source(tmp_path)

    class RateLimitedBackend(Backend):
        def create_ticket(self, ticket):
            self.created.append(ticket["metadata"]["planfile_id"])
            if len(self.created) == 2:
                error = RuntimeError("secondary rate limit; retry-after: 60")
                error.status = 403
                raise error
            return {"id": ticket["metadata"]["planfile_id"] + "-remote"}

    backend = RateLimitedBackend()
    with pytest.raises(RuntimeError, match="1 ticket") as caught:
        outbound(backend, path, data, store)

    assert caught.value.result.succeeded == ("good",)
    assert caught.value.result.failed == ("bad",)
    assert backend.created == ["good", "bad"]
    assert "sync" not in data["backlog"]["tickets"]["later"]


def test_rate_limit_error_exposes_retry_after_hint(tmp_path):
    path, data, store = source(tmp_path, ("only",))

    class RateLimitedBackend(Backend):
        def create_ticket(self, ticket):
            error = RuntimeError("secondary rate limit")
            error.status = 403
            error.headers = {"Retry-After": "37"}
            raise error

    with pytest.raises(RuntimeError, match="retry after 37s") as caught:
        outbound(RateLimitedBackend(), path, data, store)

    assert caught.value.retry_after == 37


def test_rate_limit_error_converts_absolute_reset_to_seconds(monkeypatch):
    from planfile.sync.outbound import _retry_after_seconds

    monkeypatch.setattr("planfile.sync.outbound.time.time", lambda: 1_000.0)
    error = RuntimeError("primary rate limit")
    error.headers = {"X-RateLimit-Reset": "1042"}

    assert _retry_after_seconds(error) == 42


def test_persistence_failure_propagates(tmp_path, monkeypatch):
    path, data, store = source(tmp_path, ("good",))

    def broken_save(self, mapping):
        raise OSError("controlled disk failure")

    monkeypatch.setattr(SyncState, "save_sync", broken_save)
    with pytest.raises(OSError, match="controlled disk failure"):
        outbound(Backend(), path, data, store)


def app():
    cli = typer.Typer()
    cli.command("github")(commands.github_cmd)
    cli.command("all")(commands.all_cmd)
    cli.command("watch")(commands.watch_cmd)
    return cli


@pytest.mark.parametrize("direction", ["to", "both"])
def test_cli_partial_failure_is_nonzero_without_success_or_inbound(
    tmp_path, monkeypatch, direction
):
    source(tmp_path)
    backend = Backend({"bad"})
    monkeypatch.setattr(IntegrationConfig, "get_integration_backend", lambda *args: backend)
    result = CliRunner().invoke(app(), ["github", str(tmp_path), "--direction", direction])
    assert result.exit_code == 1, result.output
    assert "completed successfully" not in result.output
    assert "Synced to external system" not in result.output
    assert not backend.fetched
    assert backend.created == ["good", "bad", "later"]


@pytest.mark.parametrize("dry_run", [False, True])
def test_cli_success_and_dry_run_still_exit_zero(tmp_path, monkeypatch, dry_run):
    source(tmp_path, ("good",))
    backend = Backend()
    monkeypatch.setattr(IntegrationConfig, "get_integration_backend", lambda *args: backend)
    args = ["github", str(tmp_path), "--direction", "to"]
    if dry_run:
        args.append("--dry-run")
    result = CliRunner().invoke(app(), args)
    assert result.exit_code == 0, result.output
    assert ("Dry run completed" if dry_run else "completed successfully") in result.output
    assert backend.created == ([] if dry_run else ["good"])


def test_sync_all_reports_nonzero_and_still_attempts_other_integrations(monkeypatch):
    seen = []

    def fake_sync(integration, *args, **kwargs):
        seen.append(integration)
        if integration == "github":
            raise typer.Exit(1)

    monkeypatch.setattr(commands, "sync_integration", fake_sync)
    monkeypatch.setattr(IntegrationConfig, "load_configs", lambda self: None)
    monkeypatch.setattr(IntegrationConfig, "has_configured_integrations", lambda self: True)
    monkeypatch.setattr(
        IntegrationConfig,
        "__init__",
        lambda self, *args: setattr(self, "config", {"integrations": {"github": {}, "jira": {}}}),
    )
    result = CliRunner().invoke(app(), ["all", "--direction", "to"])
    assert result.exit_code == 1, result.output
    assert seen == ["github", "jira"]


@pytest.mark.parametrize("fail", [False, True])
def test_watch_once_reflects_failure_without_stopping_continuous_helper(
    tmp_path, monkeypatch, fail
):
    (tmp_path / ".planfile").mkdir()
    monkeypatch.setattr(IntegrationConfig, "load_configs", lambda self: None)

    def fake_sync(*args, **kwargs):
        if fail:
            raise typer.Exit(1)

    monkeypatch.setattr(commands, "sync_integration", fake_sync)
    assert commands._run_sync_once(["github"], str(tmp_path), "to") is (not fail)
    result = CliRunner().invoke(
        app(), ["watch", str(tmp_path), "--integration", "github", "--once"]
    )
    assert result.exit_code == int(fail), result.output
