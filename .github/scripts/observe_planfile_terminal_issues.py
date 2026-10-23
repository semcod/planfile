"""Observe five qualified Issues using a disposable, inbound-only Planfile store."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

REPOSITORY = "semcod/planfile"
SELECTION = {
    "GITHUB-3": (3, "done"),
    "GITHUB-9": (9, "canceled"),
    "GITHUB-13": (13, "canceled"),
    "GITHUB-14": (14, "done"),
    "PLF-036": (15, "done"),
}
INPUTS = (
    ".planfile/config.yaml",
    ".planfile/github.planfile.yaml",
    ".planfile/sprints/backlog.yaml",
    ".planfile/sprints/current.yaml",
    ".planfile/sync/github.state.yaml",
)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def source_blob(root: Path, name: str) -> bytes:
    # Never use a developer's operational queue or inherited cache mirrors.
    return subprocess.check_output(["git", "show", "HEAD:" + name], cwd=root)


def inventory(directory: Path) -> dict[str, dict]:
    tickets: dict[str, dict] = {}
    selected_counts = dict.fromkeys(SELECTION, 0)
    for file in sorted((directory / ".planfile/sprints").glob("*.yaml")):
        data = yaml.safe_load(file.read_text()) or {}
        sprint = data.get("sprint", data)
        for ident, ticket in sprint.get("tickets", {}).items():
            if ident in selected_counts:
                selected_counts[ident] += 1
            tickets[ident] = ticket
    require(all(n == 1 for n in selected_counts.values()), "selected_identity_count")
    return tickets


def prepare_store(root: Path, destination: Path, stale: bool) -> dict[str, dict]:
    for name in INPUTS:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_blob(root, name))
    observed = inventory(destination)
    for ident, (_, expected) in SELECTION.items():
        require(observed[ident].get("id") == ident, "qualified_identity_missing")
        require(observed[ident].get("status") == expected, "qualified_state_mismatch")
    if stale:
        for file in (destination / ".planfile/sprints").glob("*.yaml"):
            data = yaml.safe_load(file.read_text())
            for ident, ticket in data["sprint"]["tickets"].items():
                if ident in SELECTION:
                    ticket["status"] = "open"
            file.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return inventory(destination)


def remote_snapshot(repository: str) -> dict[str, dict]:
    require(bool(os.environ.get("GITHUB_TOKEN")), "github_read_token_missing")
    result = {}
    for ident, (number, _) in SELECTION.items():
        request = Request(
            f"https://api.github.com/repos/{repository}/issues/{number}",
            headers={
                "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "planfile-readonly-observer",
            },
            method="GET",
        )
        with urlopen(request, timeout=30) as response:
            issue = json.load(response)
        require("pull_request" not in issue, "selected_record_is_pull_request")
        metadata = {
            "title": issue["title"],
            "body": issue.get("body"),
            "labels": sorted(label["name"] for label in issue["labels"]),
            "assignees": sorted(user["login"] for user in issue["assignees"]),
            "milestone": (issue.get("milestone") or {}).get("number"),
        }
        result[ident] = {
            "number": number,
            "state": issue["state"],
            "state_reason": issue.get("state_reason"),
            "metadata_sha256": hashlib.sha256(
                json.dumps(metadata, sort_keys=True).encode()
            ).hexdigest(),
        }
    return result


def require_terminal(snapshot: dict[str, dict]) -> None:
    require(set(snapshot) == set(SELECTION), "remote_selection_mismatch")
    for ident, (_, expected) in SELECTION.items():
        require(snapshot[ident]["state"] == "closed", "remote_no_longer_terminal")
        reason = "not_planned" if expected == "canceled" else "completed"
        require(snapshot[ident]["state_reason"] == reason, "remote_reason_changed")


def cli_command(directory: Path, dry_run: bool) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "planfile",
        "sync",
        "github",
        str(directory),
        "--repo",
        REPOSITORY,
        "--direction",
        "from",
        "--managed-only",
    ]
    for ident in SELECTION:
        command.extend(["--ticket", ident])
    if dry_run:
        command.append("--dry-run")
    return command


def invoke_cli(command: list[str]) -> None:
    subprocess.run(command, check=True)


def observe(root: Path, *, canary: bool, observation_id: str) -> dict:
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "repository_scope")
    require(
        bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}", observation_id)),
        "observation_id_invalid",
    )
    head = git_head(root)
    require(os.environ.get("GITHUB_SHA") == head, "source_revision_mismatch")
    import planfile

    require(
        Path(planfile.__file__).resolve().is_relative_to(root.resolve()), "adapter_source_mismatch"
    )
    before = remote_snapshot(REPOSITORY)
    require_terminal(before)
    phases = ("dry-run", "real", "repeat") if canary else ("real",)
    runs = []
    with tempfile.TemporaryDirectory(prefix="planfile-readonly-") as name:
        directory = Path(name)
        initial = prepare_store(root, directory, stale=canary)
        for phase in phases:
            invoke_cli(cli_command(directory, dry_run=phase == "dry-run"))
            after = inventory(directory)
            require(set(after) == set(initial), "unexpected_local_identity")
            require(
                all(
                    after[k].get("status") == row.get("status")
                    for k, row in initial.items()
                    if k not in SELECTION
                ),
                "unselected_lifecycle_change",
            )
            statuses = {key: after[key].get("status") for key in SELECTION}
            expected = (
                dict.fromkeys(SELECTION, "open")
                if phase == "dry-run"
                else {key: value[1] for key, value in SELECTION.items()}
            )
            require(statuses == expected, "local_terminal_projection_mismatch")
            runs.append({"phase": phase, "local_statuses": statuses})
    after_remote = remote_snapshot(REPOSITORY)
    require_terminal(after_remote)
    require(before == after_remote, "remote_metadata_or_state_changed")
    return {
        "schema": "planfile.github-readonly-observation/v1",
        "source_sha": head,
        "repository": REPOSITORY,
        "observation_id": observation_id,
        "canary": canary,
        "selection": list(SELECTION),
        "runs": runs,
        "remote_before": before,
        "remote_after": after_remote,
        "persistence": "disposable-local-store; no Git or provider projection",
        "result": "PASS",
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report = observe(
        root,
        canary=os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch",
        observation_id=os.environ.get("PLANFILE_OBSERVATION_ID", "scheduled"),
    )
    destination = root / ".ci-home/planfile-github-observation.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
