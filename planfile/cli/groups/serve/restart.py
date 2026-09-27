"""Identify and restart a local Docker Planfile server, never a port's arbitrary owner."""

import json
import os
import shutil
import socket
import subprocess
import time


class RestartError(RuntimeError):
    """The endpoint cannot safely be restarted."""


def _docker(*args: str) -> str:
    try:
        result = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=35,
            check=True,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise RestartError(
            "Docker restart/query failed; check the existing service state."
        ) from exc


def _is_planfile(command: list[str]) -> bool:
    # Only direct executables; a shell containing these words is not identification.
    if not command:
        return False
    executable = os.path.basename(command[0])
    if executable.startswith("python") and command[1:2] == ["-m"]:
        command = command[2:]
        executable = command[0] if command else ""
    return (executable == "uvicorn" and command[1:2] == ["planfile.api.server:app"]) or (
        executable == "planfile" and command[1:2] == ["serve"]
    )


def _matches(container: dict, host: str, port: int) -> bool:
    config = container.get("Config") or {}
    command = (config.get("Entrypoint") or []) + (config.get("Cmd") or [])
    if not container.get("State", {}).get("Running") or not _is_planfile(command):
        return False
    ports = container.get("NetworkSettings", {}).get("Ports") or {}
    return any(
        binding.get("HostPort") == str(port) and binding.get("HostIp") == host
        for name, bindings in ports.items()
        if name.endswith("/tcp")
        for binding in (bindings or [])
    )


def restart_container(host: str, port: int) -> str | None:
    """Return restarted immutable container ID, or None if no verified owner exists."""
    if not shutil.which("docker"):
        return None
    context = os.environ.get("DOCKER_CONTEXT")
    endpoint = None if context else os.environ.get("DOCKER_HOST")
    if not endpoint:
        try:
            contexts = json.loads(_docker("context", "inspect", *([context] if context else [])))
            endpoint = contexts[0]["Endpoints"]["docker"]["Host"]
        except (RestartError, ValueError, KeyError, IndexError, TypeError):
            return None
    if not endpoint.startswith("unix://"):
        return None  # A remote daemon cannot establish ownership of this host port.
    try:
        ids = _docker("ps", "--quiet", "--no-trunc", "--filter", f"publish={port}").split()
        if not ids:
            return None
        matches = [c for c in json.loads(_docker("inspect", *ids)) if _matches(c, host, port)]
    except RestartError:
        return None  # An unavailable daemon must not prevent a verified local restart.
    except (ValueError, TypeError, KeyError) as exc:
        raise RestartError("Invalid Docker ownership response; restart refused.") from exc
    if len(matches) != 1:
        return None
    container_id = matches[0]["Id"]
    current = json.loads(_docker("inspect", container_id))
    if (
        len(current) != 1
        or current[0].get("Id") != container_id
        or not _matches(current[0], host, port)
    ):
        raise RestartError("Container ownership changed; restart refused.")
    _docker("restart", "--time", "10", container_id)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        current = json.loads(_docker("inspect", container_id))[0]
        health = current.get("State", {}).get("Health", {}).get("Status")
        if _matches(current, host, port) and health in (None, "healthy"):
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    return container_id
            except OSError:
                pass
        time.sleep(0.2)
    raise RestartError("Container restart requested, but its endpoint did not become ready.")
