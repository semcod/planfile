"""Standalone copy of c2004's ticket builder for the planfile examples set.

This is a near-verbatim copy of
``c2004/monitoring/healing-webhook/ticket_builder.py`` — the file the
healing-webhook actually uses in production. Kept here so people reading
the planfile examples can grok the LLM-ready template without checking
out the c2004 monorepo.

Usage
-----
    from ticket_builder import build_ticket_payload
    alert = {
        "labels": {
            "alertname": "EndpointDown",
            "severity": "critical",
            "component": "endpoint",
            "instance": "http://localhost:8101/api/v3/devices",
        },
        "annotations": {
            "summary": "Endpoint /api/v3/devices returning 500",
            "observed": "500 Internal Server Error",
        },
        "startsAt": "2026-05-08T16:30:00Z",
    }
    payload = build_ticket_payload(alert, repo=".", source="alertmanager")
    # → dict ready for `planfile ticket create`
"""

from __future__ import annotations

import subprocess
import textwrap
from typing import Any


LLM_READY_TEMPLATE = """\
## 🚨 Context

- **Alert:** {alertname}
- **Severity:** {severity}
- **Component:** {component}
- **Stack:** c2004 monorepo (FastAPI backend + Vue/Vite frontend + connect-* microservices)
- **Repo:** {repo}
- **Commit:** `{commit}`
- **Detected at:** {timestamp}
- **Source:** {source}

{summary}

## 🔁 Reproduction

```bash
{reproduction}
```

Expected → HTTP 200 / `probe_success=1`.
Observed → `{observed}`.

## 📂 Likely-affected areas

{affected_paths}

## ✅ Acceptance criteria

Agent must leave the repo green against **all** of the following:

{acceptance_block}

## 🔒 Constraints

- Do NOT modify generated code (`**/*_pb2*.py`, `**/__generated__/**`).
- Do NOT bump dependencies in `*/requirements*.txt` without evidence.
- Do NOT disable tests or weaken assertions to pass the gate.
- Keep changes under ~80 lines; larger diffs must be split into multiple tickets.
- Always write a short regression test that would have caught this alert.

## 🤖 Prompt (LLM-agnostic — copy/paste verbatim)

> You are assigned the following ticket. Produce a minimal patch that satisfies every acceptance criterion.
>
> {prompt_body}
>
> Workflow:
> 1. Read the files listed in "Likely-affected areas".
> 2. Reproduce the failure using the `Reproduction` block.
> 3. Propose a patch; stay within the constraints.
> 4. Run `task monitor:probe` to confirm the acceptance criteria pass.
> 5. Summarise the root cause in 3 sentences for the PR description.

## 📎 Raw alert payload

```json
{raw_payload}
```
"""


def _git_commit(repo: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", repo, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return out.decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _infer_paths(component: str, labels: dict[str, str]) -> list[str]:
    if "instance" in labels and "localhost:8202" in labels["instance"]:
        return ["firmware/", "oqlos/api/"]
    if "instance" in labels and "localhost:8100" in labels["instance"]:
        return ["frontend/src/"]
    if "instance" in labels and "localhost:810" in labels["instance"]:
        return [
            "connect-*/backend/",
            "backend/api/routes/v3/",
            "packages/backend-shared-py/src/shared/",
        ]
    mapping = {
        "backend": ["backend/api/routes/", "backend/app/"],
        "endpoint": ["backend/api/routes/", "connect-*/backend/"],
        "infrastructure": ["docker-compose.yml"],
    }
    return mapping.get(component, ["backend/", "connect-*/backend/"])


def _format_paths(paths: list[str]) -> str:
    return "\n".join(f"- `{p}`" for p in paths)


def _default_acceptance(instance: str | None) -> list[str]:
    probes = [
        "GET http://localhost:8101/api/v3/health → 200",
        "`task monitor:probe` exits 0",
        "`task test` passes for affected sub-packages",
        "`redsl gate check` returns exit code 0",
    ]
    if instance:
        probes.insert(0, f"GET {instance} → 200 (was {instance} failing)")
    return probes


def _format_acceptance(items: list[str]) -> str:
    return "\n".join(f"- [ ] {x}" for x in items)


def _reproduction_for(labels: dict[str, str]) -> str:
    lines = ["task monitor:probe"]
    if "instance" in labels:
        lines.append(
            f"curl -sS -m 4 -o /dev/null -w '%{{http_code}}\\n' '{labels['instance']}'"
        )
    return "\n".join(lines)


def build_ticket_payload(alert: dict[str, Any], *, repo: str, source: str = "healing-webhook") -> dict:
    """Convert an Alertmanager alert into planfile ticket kwargs."""
    labels = alert.get("labels", {}) or {}
    annotations = alert.get("annotations", {}) or {}

    alertname = labels.get("alertname", "UnknownAlert")
    severity = labels.get("severity", "error")
    component = labels.get("component", "unknown")
    instance = labels.get("instance")
    summary = annotations.get("summary") or annotations.get("description") or "(no summary)"
    observed = annotations.get("observed") or alert.get("status") or "failing"
    timestamp = alert.get("startsAt", "")

    description = LLM_READY_TEMPLATE.format(
        alertname=alertname,
        severity=severity,
        component=component,
        repo=repo,
        commit=_git_commit(repo),
        timestamp=timestamp,
        source=source,
        summary=f"**Summary:** {summary}",
        reproduction=_reproduction_for(labels),
        observed=observed,
        affected_paths=_format_paths(_infer_paths(component, labels)),
        acceptance_block=_format_acceptance(_default_acceptance(instance)),
        prompt_body=textwrap.shorten(
            f"Alert {alertname} fired: {summary}. Component={component}, "
            f"severity={severity}. Root-cause and land a minimal, tested patch.",
            width=480,
            placeholder="…",
        ),
        raw_payload=str(alert)[:1500],
    )

    return {
        "name": f"[{source}] {alertname}: {summary[:80]}",
        "priority": {"critical": "critical", "error": "high", "warning": "normal"}.get(severity, "normal"),
        "source": source,
        "description": description,
        "labels": sorted({source, "auto-generated", "llm-ready", f"severity:{severity}", f"component:{component}"}),
    }


if __name__ == "__main__":
    # Demo — print a payload so you can eyeball the structure.
    import json

    demo = build_ticket_payload(
        {
            "labels": {
                "alertname": "EndpointDown",
                "severity": "critical",
                "component": "endpoint",
                "instance": "http://localhost:8101/api/v3/devices",
            },
            "annotations": {
                "summary": "Endpoint /api/v3/devices returning 500",
                "observed": "500 Internal Server Error",
            },
            "startsAt": "2026-05-08T16:30:00Z",
        },
        repo=".",
        source="alertmanager",
    )
    print(json.dumps({k: v for k, v in demo.items() if k != "description"}, indent=2))
    print("\n--- description ---\n")
    print(demo["description"])
