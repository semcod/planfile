"""Inbound polling exercises the actual watch loop, store and import adapter."""

import pytest
import typer

from planfile import Planfile
from planfile.cli.groups.sync import commands
from planfile.integrations.config import IntegrationConfig
from planfile.sync.base import TicketState
from planfile.sync.operations import sync_from_external


@pytest.fixture
def incoming(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    remote = TicketState(
        id="10", name="Tracked issue", status="open",
        url="https://github.com/fixture/watch/issues/10", key="fixture/watch#10",
    )
    local = pf.create_ticket(
        remote.name, sprint="backlog", integration=["github"], backend="github",
        sync={"github": {"id": remote.id, "url": remote.url, "key": remote.key}},
    )
    state = {"clock": 0, "ticks": 0, "limit": 3, "calls": [],
             "remote": [remote], "on_tick": None, "on_fetch": None, "fail": None}

    class Backend:
        config = {"repo": "fixture/watch"}

        def list_tickets(self):
            if state["fail"]:
                state["fail"]()
            if state["on_fetch"]:
                state["on_fetch"]()
            return state["remote"]

    def sync(integration, directory, dry_run, direction, **kwargs):
        assert integration == "github" and directory == str(tmp_path)
        assert direction == "from" and dry_run is False
        state["calls"].append(state["clock"])
        sync_from_external(Backend(), pf.store, False, "github")

    def sleep(seconds):
        state["clock"] += seconds
        state["ticks"] += 1
        if state["on_tick"]:
            state["on_tick"]()
        if state["ticks"] >= state["limit"]:
            raise KeyboardInterrupt

    monkeypatch.setattr(IntegrationConfig, "load_configs", lambda self: None)
    monkeypatch.setattr(commands, "sync_integration", sync)
    monkeypatch.setattr(commands.time, "monotonic", lambda: state["clock"])
    monkeypatch.setattr(commands.time, "sleep", sleep)
    state.update(pf=pf, local_id=local.id)
    state["run"] = lambda once=False: commands.watch_cmd(
        str(tmp_path), 5, ["github"], "from", once,
    )
    return state


@pytest.mark.parametrize("reason, expected", [
    ("completed", "done"), ("not_planned", "canceled"), (None, "blocked"),
])
def test_remote_only_closure_reaches_local_store(incoming, reason, expected):
    def close_remote():
        if incoming["ticks"] == 3:
            incoming["remote"][0] = incoming["remote"][0].model_copy(
                update={"status": "closed", "metadata": {"state_reason": reason}},
            )
    incoming.update(on_tick=close_remote, limit=5)
    incoming["run"]()
    assert incoming["calls"] == [0, 5, 10, 15, 20]
    local = incoming["pf"].get_ticket(incoming["local_id"])
    assert local.status.value == expected
    assert local.sync["github"]["id"] == "10"


def test_remote_only_new_issue_is_imported_once(incoming):
    def add_remote():
        if incoming["ticks"] == 3:
            incoming["remote"].append(TicketState(
                id="11", name="New remote issue", status="open",
                url="https://github.com/fixture/watch/issues/11", key="fixture/watch#11",
            ))
    incoming.update(on_tick=add_remote, limit=5)
    incoming["run"]()
    tickets = incoming["pf"].list_tickets(sprint="all")
    imported = [t for t in tickets if str(t.sync.get("github", {}).get("id")) == "11"]
    assert len(imported) == 1 and imported[0].status.value == "open"
    assert incoming["calls"] == [0, 5, 10, 15, 20]


def test_idle_inbound_polls_at_configured_interval(incoming):
    incoming["run"]()
    assert incoming["calls"] == [0, 5, 10]


def test_remote_poll_failure_retries_with_backoff_without_local_edit(incoming):
    def fail_second():
        if len(incoming["calls"]) == 2:
            raise RuntimeError("controlled provider outage")
    incoming.update(fail=fail_second, limit=9)
    incoming["run"]()
    assert incoming["calls"] == [0, 5, 35, 40]


def test_inbound_provider_cooldown_limits_remote_polling(incoming):
    class ProviderCooldown(Exception):
        retry_after = 90

    def fail_first():
        if len(incoming["calls"]) == 1:
            raise ProviderCooldown("controlled provider cooldown")
    incoming.update(fail=fail_first, limit=20)
    incoming["run"]()
    assert incoming["calls"] == [0, 90, 95]


def test_local_edit_during_remote_fetch_survives_that_import(incoming):
    def edit_during_fetch():
        if len(incoming["calls"]) == 2:
            incoming["pf"].update_ticket(incoming["local_id"], name="Concurrent local edit")
    incoming.update(on_fetch=edit_during_fetch, limit=2)
    incoming["run"]()
    assert incoming["calls"] == [0, 5]
    assert incoming["pf"].get_ticket(incoming["local_id"]).name == "Concurrent local edit"


def test_inbound_once_failure_remains_nonzero(incoming):
    def fail():
        raise RuntimeError("controlled provider outage")
    incoming["fail"] = fail
    with pytest.raises(typer.Exit) as caught:
        incoming["run"](once=True)
    assert caught.value.exit_code == 1
    assert incoming["calls"] == [0]


def test_failed_lazy_remote_result_preserves_local_ticket(incoming, capsys):
    remote = incoming["remote"][0]

    def broken_result():
        yield remote
        raise RuntimeError("fixture-provider-private-detail")

    before = incoming["pf"].get_ticket(incoming["local_id"]).model_dump(mode="json")
    incoming["remote"] = broken_result()
    with pytest.raises(typer.Exit) as caught:
        incoming["run"](once=True)
    assert caught.value.exit_code == 1
    assert incoming["pf"].get_ticket(incoming["local_id"]).model_dump(mode="json") == before
    assert "fixture-provider-private-detail" not in capsys.readouterr().out


def test_empty_remote_response_is_successful_and_preserves_local_ticket(incoming):
    incoming["remote"] = []
    before = incoming["pf"].get_ticket(incoming["local_id"]).model_dump(mode="json")
    incoming["run"](once=True)
    assert incoming["calls"] == [0]
    assert incoming["pf"].get_ticket(incoming["local_id"]).model_dump(mode="json") == before
