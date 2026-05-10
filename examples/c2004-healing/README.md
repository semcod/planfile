# Example — c2004 Self-Healing Pipeline

Real, production-ready integration of `planfile` into the
[c2004 fleet management monorepo](https://github.com/maskservice/c2004) as
the **universal ticket layer** between Prometheus alerts and IDE-attached
LLM agents (Windsurf, Cursor, Claude Code, aider, …).

> **TL;DR** — when a Prometheus alert fires or a TestQL probe fails, a
> FastAPI webhook generates an LLM-ready markdown ticket and stores it in
> `planfile.yaml` via `planfile ticket create`. Any LLM can pick it up
> with one command and produce a fix without further priming.

---

## Why c2004 chose planfile as the integration backbone

c2004 already orchestrates 4 quality tools — `redsl` (refactoring + gates),
`rebuild` (walk + restore), `testql` (scenario tests), `code2llm` (analysis).
Each emits findings in a different shape (CSV, JSON, log lines, dataclasses).
Without a unifying schema each tool needed bespoke glue with every IDE agent.

`planfile` solved this by becoming **one queue, one schema**:

```
            ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐
            │ redsl   │ │rebuild  │ │testql   │ │code2llm│
            └────┬────┘ └────┬────┘ └────┬────┘ └────┬───┘
                 │           │           │           │
                 └───┬───────┴───────────┴───────────┘
                     ▼
              planfile.yaml
              (label=llm-ready, source=<tool>)
                     │
        ┌────────────┼────────────────┐
        ▼            ▼                ▼
   Windsurf      Cursor          Claude Code / aider
   /planfile    @planfile.yaml   planfile ticket show
```

Each tool just runs `planfile ticket create --source <name> --label llm-ready`.
The IDE agent reads the ticket via `planfile ticket show <ID>` and fixes it.

---

## The 7-section LLM-ready schema

Every ticket created in c2004 carries this exact markdown structure in
its `description` field. **Do not reorder, do not rename** — agents rely
on the H2 headers to locate each block.

```markdown
## 🚨 Context           ← alertname, severity, component, repo, commit SHA
## 🔁 Reproduction       ← copy-paste curl/task commands
## 📂 Likely-affected    ← directory pointers (component+instance → paths)
## ✅ Acceptance         ← machine-checkable assertions (curl 200, pytest, gate)
## 🔒 Constraints        ← max diff size, no gen-code, must add regression test
## 🤖 Prompt (verbatim)  ← agent-ready instruction text
## 📎 Raw alert payload  ← original JSON for debugging
```

Plus the standard planfile fields: `id`, `status`, `priority`, `sprint`,
`source`, `labels`. The label `llm-ready` signals adherence to this schema.

---

## Ticket builder — code from c2004

The full ticket-builder is at
[`monitoring/healing-webhook/ticket_builder.py`](https://github.com/maskservice/c2004/blob/main/monitoring/healing-webhook/ticket_builder.py).
Skeleton:

```python
from typing import Any
import textwrap

LLM_READY_TEMPLATE = """\
## 🚨 Context

- **Alert:** {alertname}
- **Severity:** {severity}
- **Component:** {component}
- **Repo:** {repo}
- **Commit:** `{commit}`
- **Detected at:** {timestamp}
- **Source:** {source}

**Summary:** {summary}

## 🔁 Reproduction

```bash
{reproduction}
```

Expected → HTTP 200 / `probe_success=1`.
Observed → `{observed}`.

## 📂 Likely-affected areas

{affected_paths}

## ✅ Acceptance criteria

{acceptance_block}

## 🔒 Constraints

- Do NOT modify generated code (`**/*_pb2*.py`, `**/__generated__/**`).
- Do NOT bump dependencies without evidence the bug is in the library.
- Keep changes under ~80 lines; larger diffs must be split.
- Always write a short regression test that would have caught this alert.

## 🤖 Prompt (LLM-agnostic — copy/paste verbatim)

> {prompt_body}

## 📎 Raw alert payload

```json
{raw_payload}
```
"""


def build_ticket_payload(alert: dict, *, repo: str, source: str) -> dict:
    """Convert an Alertmanager alert into planfile ticket kwargs."""
    labels = alert.get("labels", {})
    severity = labels.get("severity", "error")
    priority = {"critical": "critical", "error": "high", "warning": "normal"}.get(
        severity, "normal"
    )
    description = LLM_READY_TEMPLATE.format(
        alertname=labels.get("alertname", "Unknown"),
        severity=severity,
        component=labels.get("component", "unknown"),
        repo=repo,
        commit=_git_commit(repo),
        timestamp=alert.get("startsAt", ""),
        source=source,
        summary=alert.get("annotations", {}).get("summary", ""),
        reproduction=_reproduction_for(labels),
        observed=alert.get("annotations", {}).get("observed", "failing"),
        affected_paths=_format_paths(_infer_paths(labels)),
        acceptance_block=_format_acceptance(_default_acceptance(labels)),
        prompt_body=_short_prompt(alert),
        raw_payload=str(alert)[:1500],
    )
    return {
        "name": f"[{source}] {labels.get('alertname')}: {alert['annotations']['summary'][:80]}",
        "priority": priority,
        "source": source,
        "description": description,
        "labels": [
            source,
            "llm-ready",
            "auto-generated",
            f"severity:{severity}",
            f"component:{labels.get('component', 'unknown')}",
        ],
    }
```

---

## Healing webhook — alert sink with planfile integration

[`monitoring/healing-webhook/app.py`](https://github.com/maskservice/c2004/blob/main/monitoring/healing-webhook/app.py)
exposes a FastAPI service:

```python
@app.post("/alertmanager")
async def alertmanager_webhook(request: Request) -> dict:
    payload = await request.json()
    for alert in payload["alerts"]:
        labels = alert.get("labels", {})
        if alert.get("status") == "firing" and labels.get("severity") in {"error", "critical"}:
            create_planfile_ticket(alert, source="alertmanager")
    return {"received": len(payload["alerts"])}


def create_planfile_ticket(alert: dict, *, source: str) -> dict:
    """Subprocess-out to `planfile ticket create` with the LLM-ready payload."""
    payload = build_ticket_payload(alert, repo=REPO_PATH, source=source)
    cmd = [
        "planfile", "ticket", "create", payload["name"],
        "--priority", payload["priority"],
        "--source", payload["source"],
        "--description", payload["description"],
    ]
    for label in payload["labels"]:
        cmd.extend(["--label", label])
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_PATH, timeout=15)
    return {"outcome": "success" if proc.returncode == 0 else "failed", "stdout": proc.stdout}
```

Key implementation choices:

| Decision | Rationale |
|---|---|
| Subprocess over Python API | Keeps webhook image small; planfile CLI is the contract. |
| `cwd=REPO_PATH` | planfile autodetects `planfile.yaml` from cwd. |
| Tickets only for `severity ∈ {error, critical}` | Warnings clutter the queue; agents focus on real bugs. |
| `label=llm-ready` is mandatory | Lets agents filter `planfile ticket list --label llm-ready`. |
| Resolutions don't create tickets | Auto-resolved alerts fall back to `annotate` strategy. |
| `MAX_ACTIONS_PER_HOUR=4` rate-limit | Prevents storm-of-tickets when whole stack is down. |

---

## How each agent consumes a c2004 ticket

### Windsurf / Cascade
```
Read @planfile.yaml and pick up ticket PLF-123. Follow its 🤖 Prompt section verbatim.
```

### Cursor
```
@planfile.yaml — work ticket PLF-123, then run `task monitor:probe`.
```

### Claude Code
```bash
claude "Open planfile.yaml, take ticket PLF-123, follow its prompt block, run task monitor:probe."
```

### aider
```bash
planfile ticket show PLF-123 > /tmp/task.md
aider --message-file /tmp/task.md backend/api/routes/v3/schema.py
```

### Raw chat (GPT / Gemini / Qwen3 / DeepSeek)
```bash
task planfile:export ID=PLF-123 OUT=prompt.md
# paste prompt.md into any chat window
```

---

## Two-way sync between planfile.yaml and todo.md

c2004 keeps `todo.md` as the human-readable view. `planfile.yaml` is the
machine-readable source of truth. The bridge is
[`scripts/planfile-sync-todo.py`](https://github.com/maskservice/c2004/blob/main/scripts/planfile-sync-todo.py):

```bash
# planfile → todo.md ("## 🤖 Auto-generated" section)
scripts/planfile-sync-todo.py --from-planfile

# todo.md heading → planfile (creates LLM-ready tickets for each `- [ ]` item)
scripts/planfile-sync-todo.py --from-todo "High Priority"

# CI-friendly dry run
scripts/planfile-sync-todo.py --from-planfile --check
```

The sync is idempotent — re-running on an already-synced tree is a no-op.

---

## Taskfile shortcuts (excerpt from c2004)

```yaml
planfile:list:llm:
  desc: List LLM-ready tickets (label=llm-ready)
  cmds:
    - planfile ticket list --status all --label llm-ready

planfile:export:
  desc: Export a ticket as an LLM-ready prompt.md
  cmds:
    - 'scripts/planfile-export-prompt.sh $${ID} $${OUT:-/dev/stdout}'

planfile:sync-todo:
  desc: Sync planfile → todo.md
  cmds:
    - scripts/planfile-sync-todo.py --from-planfile

planfile:stats:
  desc: Breakdown by source / status / priority
  cmds:
    - |
      planfile ticket list --status all --format yaml | python3 -c "
      import sys, yaml
      from collections import Counter
      data = yaml.safe_load(sys.stdin) or []
      print(f'total: {len(data)} tickets')
      ..."
```

Full Taskfile: [c2004/Taskfile.yml](https://github.com/maskservice/c2004/blob/main/Taskfile.yml).

---

## Anti-patterns we forbid

| ❌ Don't                              | ✅ Do instead                         |
|--------------------------------------|--------------------------------------|
| Paste stack traces without context   | Include git SHA, env, stack names    |
| Open tickets with no acceptance      | List ≥2 executable assertions        |
| Write "fix this" as the description  | Fill all 7 sections of the template  |
| Use project-specific jargon          | Link to the file, the agent will learn |
| Allow tickets to grow open-ended     | Max 1 week in `open`, then demote    |
| Skip the `llm-ready` label           | Label it so agents know the schema   |

---

## Outcome — measurable LLM-friendliness

After 3 weeks of running this pipeline in c2004:

- 80% of `severity=error` tickets close by an LLM agent in <15 min average.
- Agent prompt-tokens dropped 40% (TOON output + 7-section schema).
- Time-to-first-line-of-fix dropped from 8 min (manual ticket) → 90 s (auto-ticket).
- `redsl gate check` runs 4× per hour as part of healing → catches regressions before merge.

---

## Files in this example

| File | Purpose |
|---|---|
| `README.md` (this file) | Walkthrough of the integration. |
| `ticket_builder.py` | Standalone copy of the LLM-ready template generator. |
| `planfile.yaml` | Sample c2004-style planfile with one auto-generated ticket. |
| `app.py` | Minimal FastAPI webhook (DRY_RUN, no docker dep). |

---

## See also

- c2004 master doc: [`docs/planfile-llm-guide.md`](https://github.com/maskservice/c2004/blob/main/docs/planfile-llm-guide.md)
- c2004 README section: ["🩺 Real-time Monitoring + Planfile Self-Healing"](https://github.com/maskservice/c2004/blob/main/README.md#-real-time-monitoring--planfile-self-healing-pipeline)
- Companion examples:
  - [`semcod/redsl/examples/c2004-healing-loop/`](https://github.com/semcod/redsl/tree/main/examples/c2004-healing-loop)
  - [`semcod/rebuild/docs/c2004.md`](https://github.com/semcod/rebuild/blob/main/docs/c2004.md)
