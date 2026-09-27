"""Same-port restart regression tests, including real isolated listener processes."""

import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from planfile.cli.groups.serve import commands, local, restart


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(local, "restart_container", lambda *args: None)
    return tmp_path


@pytest.fixture(autouse=True)
def isolated_docker_environment(monkeypatch):
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)


def free_port():
    with socket.create_server(("127.0.0.1", 0)) as sock:
        return sock.getsockname()[1]


def container(port=8765, command=None):
    return {
        "Id": "a" * 64,
        "Config": {"Entrypoint": None, "Cmd": command or ["uvicorn", "planfile.api.server:app"]},
        "State": {"Running": True},
        "NetworkSettings": {
            "Ports": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
        },
    }


def test_free_port_is_reserved_and_stale_record_replaced(state):
    port = free_port()
    with local.serve_endpoint("127.0.0.1", port) as (listener, docker):
        assert docker is None
        assert listener.getsockname() == ("127.0.0.1", port)
        with pytest.raises(OSError):
            socket.create_server(("127.0.0.1", port))
    with local.serve_endpoint("127.0.0.1", port) as (listener, _):
        assert listener.getsockname()[1] == port


def test_unrelated_listener_is_preserved(state):
    with socket.create_server(("127.0.0.1", 0)) as other:
        port = other.getsockname()[1]
        with pytest.raises(restart.RestartError, match="unverified service"):
            with local.serve_endpoint("127.0.0.1", port):
                pytest.fail("unrelated listener was replaced")
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux pidfds required")
def test_real_process_is_replaced_on_same_port(state):
    port = free_port()
    source = """
import time
from planfile.cli.groups.serve.local import serve_endpoint
with serve_endpoint("127.0.0.1", PORT) as (sock, _):
    print("ready", flush=True)
    time.sleep(30)
""".replace("PORT", str(port))
    child = subprocess.Popen([sys.executable, "-c", source], stdout=subprocess.PIPE, text=True)
    try:
        import select

        assert select.select([child.stdout], [], [], 10)[0], "listener startup timed out"
        assert child.stdout.readline().strip() == "ready"
        with local.serve_endpoint("127.0.0.1", port) as (listener, _):
            assert child.wait(timeout=5) == -signal.SIGTERM
            assert listener.getsockname()[1] == port
            record = json.loads(next((state / "planfile/serve").glob("*.json")).read_text())
            assert record["pid"] == os.getpid()
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)


@pytest.mark.parametrize("change", [{"start": "invalid"}, {"project": "/other"}, {"pid": 1}])
def test_stale_or_wrong_owner_never_signaled(state, monkeypatch, change):
    path = state / "owner.json"
    owner = {
        "pid": os.getppid(),
        "start": "old",
        "host": "127.0.0.1",
        "port": 8765,
        "project": str(Path.cwd().resolve()),
    }
    owner.update(change)
    path.write_text(json.dumps(owner))
    monkeypatch.setattr(signal, "pidfd_send_signal", lambda *a: pytest.fail("unverified signal"))
    with pytest.raises(restart.RestartError):
        local._stop_recorded(path, "127.0.0.1", 8765)


@pytest.mark.parametrize(
    "command",
    [
        ["uvicorn", "other:app"],
        ["sh", "-c", "uvicorn planfile.api.server:app"],
        ["echo", "planfile", "serve"],
        ["python", "-m", "http.server"],
    ],
)
def test_unrelated_container_commands_are_refused(command):
    assert not restart._matches(container(command=command), "127.0.0.1", 8765)


def test_container_address_and_transport_must_match():
    value = container()
    assert restart._matches(value, "127.0.0.1", 8765)
    assert not restart._matches(value, "127.0.0.1", 8766)
    assert not restart._matches(value, "0.0.0.0", 8765)
    value["NetworkSettings"]["Ports"] = {"8000/udp": [{"HostIp": "127.0.0.1", "HostPort": "8765"}]}
    assert not restart._matches(value, "127.0.0.1", 8765)


def docker_mock(monkeypatch, inspections):
    calls = []
    values = iter(inspections)
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setattr(restart.shutil, "which", lambda _: "/usr/bin/docker")

    def docker(*args):
        calls.append(args)
        if args[0] == "ps":
            return "a" * 64
        if args[0] == "inspect":
            return json.dumps(next(values))
        if args[0] == "restart":
            return "a" * 64
        pytest.fail(f"unexpected command: {args}")

    monkeypatch.setattr(restart, "_docker", docker)
    return calls


def test_docker_restarts_exact_id_and_waits_for_endpoint(monkeypatch):
    from contextlib import nullcontext

    value = container()
    calls = docker_mock(monkeypatch, [[value], [value], [value]])
    monkeypatch.setattr(restart.socket, "create_connection", lambda *a, **kw: nullcontext())
    assert restart.restart_container("127.0.0.1", 8765) == "a" * 64
    assert ("restart", "--time", "10", "a" * 64) in calls
    assert len([c for c in calls if c[0] == "restart"]) == 1


@pytest.mark.parametrize("matches", [[], [container(), container()]])
def test_missing_or_ambiguous_docker_owner_is_not_restarted(monkeypatch, matches):
    calls = docker_mock(monkeypatch, [matches])
    assert restart.restart_container("127.0.0.1", 8765) is None
    assert not any(c[0] == "restart" for c in calls)


def test_docker_changed_ownership_refused(monkeypatch):
    calls = docker_mock(monkeypatch, [[container()], [container(port=8888)]])
    with pytest.raises(restart.RestartError, match="ownership changed"):
        restart.restart_container("127.0.0.1", 8765)
    assert not any(c[0] == "restart" for c in calls)


def test_remote_docker_is_not_considered(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote:2375")
    monkeypatch.setattr(restart.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(restart, "_docker", lambda *a: pytest.fail("remote daemon queried"))
    assert restart.restart_container("127.0.0.1", 8765) is None


def test_remote_context_overrides_local_docker_host(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setenv("DOCKER_CONTEXT", "remote")
    monkeypatch.setattr(restart.shutil, "which", lambda _: "/usr/bin/docker")

    def query(*args):
        assert args == ("context", "inspect", "remote")
        return json.dumps([{"Endpoints": {"docker": {"Host": "ssh://remote"}}}])

    monkeypatch.setattr(restart, "_docker", query)
    assert restart.restart_container("127.0.0.1", 8765) is None


def test_docker_failure_is_reported_without_starting_replacement(monkeypatch):
    monkeypatch.setattr(
        restart.subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired("docker", 35)),
    )
    with pytest.raises(restart.RestartError, match="Docker restart/query failed"):
        restart._docker("restart", "container-id")


def invoke(monkeypatch, **kwargs):
    import typer

    app = typer.Typer()
    app.command()(commands.serve_cli)
    return CliRunner().invoke(app, ["--port", "8765", *kwargs.get("args", [])])


def test_cli_container_restart_does_not_launch_uvicorn(monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def endpoint(*a):
        yield None, "a" * 64

    monkeypatch.setattr(commands, "serve_endpoint", endpoint)
    monkeypatch.setitem(
        sys.modules, "uvicorn", SimpleNamespace(run=lambda *a, **kw: pytest.fail("second server"))
    )
    result = invoke(monkeypatch)
    assert result.exit_code == 0, result.output
    assert "Restarted Planfile Docker" in result.output


def test_cli_passes_reserved_socket_and_reload(monkeypatch, state):
    captured = {}

    def run(*a, **kw):
        captured.update(kw)
        assert os.fstat(kw["fd"])

    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=run))
    import typer

    app = typer.Typer()
    app.command()(commands.serve_cli)
    result = CliRunner().invoke(app, ["--port", "0", "--reload", "--workers", "3"])
    assert result.exit_code == 0, result.output
    assert captured["reload"] and captured["workers"] == 1


def test_cli_restart_failure_returns_nonzero(monkeypatch):
    def fail(*a):
        raise restart.RestartError("ownership changed")

    monkeypatch.setattr(commands, "serve_endpoint", fail)
    result = invoke(monkeypatch)
    assert result.exit_code == 1
    assert "ownership changed" in result.output


def test_unavailable_docker_allows_local_owner_resolution(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setattr(restart.shutil, "which", lambda _: "/usr/bin/docker")

    def unavailable(*args):
        raise restart.RestartError("daemon unavailable")

    monkeypatch.setattr(restart, "_docker", unavailable)
    assert restart.restart_container("127.0.0.1", 8765) is None


def test_container_readiness_timeout_is_failure(monkeypatch):
    value = container()
    calls = docker_mock(monkeypatch, [[value], [value]])
    ticks = iter([0, 16])
    monkeypatch.setattr(restart.time, "monotonic", lambda: next(ticks))
    with pytest.raises(restart.RestartError, match="did not become ready"):
        restart.restart_container("127.0.0.1", 8765)
    assert ("restart", "--time", "10", "a" * 64) in calls


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux local restart")
def test_two_real_cli_invocations_serve_http_on_same_port(tmp_path):
    import time
    import urllib.request

    port = free_port()
    root = str(Path(__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONPATH": root, "XDG_STATE_HOME": str(tmp_path / "state")}
    children = []

    def start():
        log = (tmp_path / f"server-{len(children)}.log").open("w")
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "planfile", "serve", "--port", str(port)],
                cwd=tmp_path,
                env=env,
                stdout=log,
                stderr=log,
            )
        finally:
            log.close()
        children.append(proc)
        return proc

    def ready(proc):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            assert proc.poll() is None, (
                tmp_path / f"server-{children.index(proc)}.log"
            ).read_text()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/openapi.json", timeout=0.5
                ) as response:
                    assert "paths" in json.load(response)
                    return
            except OSError:
                time.sleep(0.1)
        pytest.fail("HTTP startup timed out")

    try:
        first = start()
        ready(first)
        second = start()
        first.wait(timeout=20)
        ready(second)
        assert second.poll() is None
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            child.wait(timeout=10)
