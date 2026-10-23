"""Optional, bounded advisory projection for new ticket descriptions."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from planfile.core.models import Ticket

ASSESSMENT_SECONDS = 1.0
BULK_SECONDS = 5.0
MAX_OUTPUT_BYTES = 65536
ADVISORY_HEADING = "**Ticket impact radar (advisory)**"


def _bundle(payload: bytes, root: Path, deadline: float) -> bytes:
    """Bound pipe reads and writes together, including a stalled stdin reader."""
    with subprocess.Popen(
        ["ticket-radar", "-", "--repository-root", str(root)],
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
    ) as process:
        try:
            output = bytearray()
            pending = memoryview(payload)
            with selectors.DefaultSelector() as selector:
                os.set_blocking(process.stdin.fileno(), False)
                os.set_blocking(process.stdout.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE)
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("radar deadline")
                    for key, _ in selector.select(remaining):
                        if key.fileobj is process.stdin:
                            written = os.write(process.stdin.fileno(), pending[:4096])
                            pending = pending[written:]
                            if not pending:
                                selector.unregister(process.stdin)
                                process.stdin.close()
                        else:
                            chunk = os.read(
                                process.stdout.fileno(),
                                min(4096, MAX_OUTPUT_BYTES - len(output) + 1),
                            )
                            if len(output) + len(chunk) > MAX_OUTPUT_BYTES:
                                raise ValueError("radar output limit")
                            output.extend(chunk)
                            if not chunk:
                                selector.unregister(process.stdout)
            if process.wait(timeout=max(0, deadline - time.monotonic())) != 0:
                raise ValueError("radar process failed")
            return bytes(output)
        finally:
            # Also stop descendants that may have inherited the pipes.
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()


def _advisory(raw: bytes, ticket_id: str) -> str:
    bundle = json.loads(raw)
    if not isinstance(bundle, dict) or bundle.get("schema") != "subactor.ticket-radar-bundle/v1":
        raise ValueError("unsupported radar bundle")
    assessment = json.loads(bundle["jsonl"])
    if (
        not isinstance(assessment, dict)
        or assessment.get("schema") != "subactor.ticket-radar/v1"
        or assessment.get("ticket_ref") != ticket_id
    ):
        raise ValueError("unsupported or mismatched radar assessment")
    complexity = assessment.get("complexity")
    score = assessment.get("score")
    minutes = assessment["estimate"]["minutes"]
    split = assessment["split"]["recommended"]
    if (
        complexity not in ("XS", "S", "M", "L")
        or type(score) is not int
        or not 0 <= score <= 100
        or type(minutes) is not int
        or not 1 <= minutes <= 240
        or type(split) is not bool
    ):
        raise ValueError("invalid radar metrics")
    return (
        f"\n\n{ADVISORY_HEADING}\n\n"
        f"- Complexity: `{complexity}`\n"
        f"- Score: `{score}/100`\n"
        f"- Estimated effort: `{minutes} min`\n"
        f"- Split recommended: `{'yes' if split else 'no'}`\n\n"
        "This estimate does not grant execution, review or merge authority."
    )


def _enrich_description(ticket: Ticket, root: Path, *, deadline: float | None = None) -> None:
    """Accept only scalar advisory metrics; all radar failures leave text intact."""
    if ADVISORY_HEADING.casefold() in ticket.description.casefold():
        return
    started = time.monotonic()
    deadline = (
        min(deadline, started + ASSESSMENT_SECONDS)
        if deadline is not None
        else started + ASSESSMENT_SECONDS
    )
    if deadline <= started:
        return
    try:
        payload = json.dumps(
            {
                "id": ticket.id,
                "title": ticket.name,
                "description": ticket.description,
                "acceptance_criteria": ticket.acceptance_criteria,
                "files": list(
                    dict.fromkeys([*ticket.files, *([ticket.file] if ticket.file else [])])
                ),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        block = _advisory(_bundle(payload, root, deadline), ticket.id)
        if len(block) <= 512:
            ticket.description += block
    except (OSError, ValueError, TypeError, KeyError, RecursionError, subprocess.SubprocessError):
        # Advisory availability and untrusted output never govern persistence.
        return
